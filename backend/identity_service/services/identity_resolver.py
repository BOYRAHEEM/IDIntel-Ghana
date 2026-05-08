"""Identity resolution: query multiple sources and return a merged verified profile."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.models.identity import DocumentStatus, IdentityRecord, VerificationStatus
from ...shared.utils.encryption import (
    GhanaCardValidator,
    decrypt_pii_field,
    encrypt_pii_field,
    make_search_hash,
)


@dataclass
class ResolverResult:
    status: str
    confidence: float
    identity: IdentityRecord | None
    primary_key_value: str | None = None
    sources_checked: list[str] = field(default_factory=list)


@dataclass
class SearchCandidate:
    idintel_id: str
    full_name: str
    confidence_score: float
    match_fields: list[str]
    ghana_card_status: str


class IdentityResolver:
    """
    Resolves identity queries against multiple data sources in priority order:
    1. Local cache (PostgreSQL with encrypted fields)
    2. NIA / Ghana Card live lookup
    3. GIS (Passport)
    4. Elasticsearch fuzzy search
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._nia_client = _get_nia_client()
        self._es_client = _get_elasticsearch_client()

    async def resolve(
        self,
        query: Any,
        institution: dict,
        requesting_user: str,
    ) -> ResolverResult:
        """Main resolution entry point."""
        query_type = query.query_type

        if query_type == "ghana_card" and query.ghana_card_number:
            return await self._resolve_by_ghana_card(
                GhanaCardValidator.normalize(query.ghana_card_number),
                institution,
            )

        if query_type == "passport" and query.passport_number:
            return await self._resolve_by_passport(query.passport_number, institution)

        if query_type == "phone_number" and query.phone_number:
            return await self._resolve_by_phone(query.phone_number, institution)

        if query_type in ("name_dob", "multi_identifier"):
            return await self._resolve_by_name_dob(
                query.full_name, query.date_of_birth, institution
            )

        return ResolverResult(status="NOT_FOUND", confidence=0.0, identity=None)

    async def _resolve_by_ghana_card(
        self, card_number: str, institution: dict
    ) -> ResolverResult:
        card_hash = make_search_hash(card_number)

        # 1. Check local cache
        result = await self._db.execute(
            select(IdentityRecord).where(IdentityRecord.ghana_card_hash == card_hash)
        )
        cached = result.scalar_one_or_none()

        if cached and self._is_cache_fresh(cached):
            return ResolverResult(
                status="VERIFIED" if cached.nia_verified else "PARTIAL_MATCH",
                confidence=cached.overall_confidence,
                identity=cached,
                primary_key_value=card_number,
                sources_checked=cached.data_sources,
            )

        # 2. Live NIA lookup
        nia_data = await self._nia_client.lookup_by_ghana_card(card_number)
        if nia_data is None:
            if cached:
                return ResolverResult(
                    status="PARTIAL_MATCH",
                    confidence=0.7,
                    identity=cached,
                    primary_key_value=card_number,
                    sources_checked=["LOCAL_CACHE"],
                )
            return ResolverResult(status="NOT_FOUND", confidence=0.0, identity=None, primary_key_value=card_number)

        # 3. Upsert to local cache
        identity = await self._upsert_from_nia(cached, nia_data, card_number, card_hash)

        return ResolverResult(
            status="VERIFIED",
            confidence=0.99,
            identity=identity,
            primary_key_value=card_number,
            sources_checked=["NIA"],
        )

    async def _resolve_by_passport(
        self, passport_number: str, institution: dict
    ) -> ResolverResult:
        passport_hash = make_search_hash(passport_number)

        result = await self._db.execute(
            select(IdentityRecord).where(IdentityRecord.passport_hash == passport_hash)
        )
        cached = result.scalar_one_or_none()

        if cached:
            return ResolverResult(
                status="VERIFIED",
                confidence=0.97,
                identity=cached,
                primary_key_value=passport_number,
                sources_checked=cached.data_sources,
            )

        return ResolverResult(status="NOT_FOUND", confidence=0.0, identity=None, primary_key_value=passport_number)

    async def _resolve_by_phone(
        self, phone: str, institution: dict
    ) -> ResolverResult:
        phone_hash = make_search_hash(phone)

        result = await self._db.execute(
            select(IdentityRecord).where(IdentityRecord.phone_hash == phone_hash)
        )
        identity = result.scalar_one_or_none()

        if identity:
            return ResolverResult(
                status="VERIFIED",
                confidence=0.87,
                identity=identity,
                primary_key_value=phone,
                sources_checked=["LOCAL_CACHE"],
            )

        return ResolverResult(status="NOT_FOUND", confidence=0.0, identity=None, primary_key_value=phone)

    async def _resolve_by_name_dob(
        self, full_name: str | None, dob: date | None, institution: dict
    ) -> ResolverResult:
        if not full_name or not dob:
            return ResolverResult(status="NOT_FOUND", confidence=0.0, identity=None)

        candidates = await self.fuzzy_search(
            full_name=full_name,
            date_of_birth=dob,
            max_results=1,
            min_confidence=0.90,
            institution=institution,
        )

        if not candidates:
            return ResolverResult(status="NOT_FOUND", confidence=0.0, identity=None)

        best = candidates[0]
        if best.confidence_score >= 0.90:
            result = await self._db.execute(
                select(IdentityRecord).where(IdentityRecord.idintel_id == best.idintel_id)
            )
            identity = result.scalar_one_or_none()
            return ResolverResult(
                status="VERIFIED" if best.confidence_score >= 0.95 else "PARTIAL_MATCH",
                confidence=best.confidence_score,
                identity=identity,
                primary_key_value=full_name,
                sources_checked=["ELASTICSEARCH"],
            )

        return ResolverResult(status="NOT_FOUND", confidence=0.0, identity=None)

    async def fuzzy_search(
        self,
        full_name: str,
        date_of_birth: date | None = None,
        gender: str | None = None,
        region: str | None = None,
        max_results: int = 5,
        min_confidence: float = 0.80,
        institution: dict | None = None,
    ) -> list[SearchCandidate]:
        """Fuzzy name search via Elasticsearch with Jaro-Winkler scoring."""
        must_clauses = [
            {
                "multi_match": {
                    "query": full_name,
                    "fields": ["full_name^3", "full_name.phonetic^2"],
                    "fuzziness": "AUTO",
                    "type": "best_fields",
                }
            }
        ]

        if date_of_birth:
            must_clauses.append({"term": {"date_of_birth": str(date_of_birth)}})
        if gender:
            must_clauses.append({"term": {"gender": gender}})
        if region:
            must_clauses.append({"term": {"region": region}})

        es = self._es_client
        try:
            response = await es.search(
                index="identities",
                body={
                    "query": {"bool": {"must": must_clauses}},
                    "size": max_results,
                    "_source": ["idintel_id", "full_name", "ghana_card_status"],
                },
            )
        except Exception:
            return []

        candidates = []
        for hit in response.get("hits", {}).get("hits", []):
            score = _normalize_es_score(hit["_score"], response["hits"]["max_score"])
            if score >= min_confidence:
                source = hit["_source"]
                candidates.append(
                    SearchCandidate(
                        idintel_id=source["idintel_id"],
                        full_name=source["full_name"],
                        confidence_score=round(score, 3),
                        match_fields=_infer_match_fields(full_name, date_of_birth, source),
                        ghana_card_status=source.get("ghana_card_status", "UNKNOWN"),
                    )
                )
        return candidates

    async def get_by_idintel_id(
        self, idintel_id: str, institution: dict
    ) -> IdentityRecord | None:
        result = await self._db.execute(
            select(IdentityRecord).where(IdentityRecord.idintel_id == idintel_id)
        )
        return result.scalar_one_or_none()

    def _is_cache_fresh(self, record: IdentityRecord, max_age_hours: int = 24) -> bool:
        if record.nia_last_sync_at is None:
            return False
        age = datetime.now(timezone.utc) - record.nia_last_sync_at.replace(tzinfo=timezone.utc)
        return age.total_seconds() < max_age_hours * 3600

    async def _upsert_from_nia(
        self,
        existing: IdentityRecord | None,
        nia_data: dict,
        card_number: str,
        card_hash: str,
    ) -> IdentityRecord:
        idintel_id = existing.idintel_id if existing else f"idig-GH-{uuid.uuid4().hex[:10].upper()}"

        record = existing or IdentityRecord(
            id=uuid.uuid4(),
            idintel_id=idintel_id,
        )

        record.full_name_encrypted = encrypt_pii_field(nia_data.get("full_name", ""))
        record.date_of_birth_encrypted = encrypt_pii_field(str(nia_data.get("date_of_birth", "")))
        record.ghana_card_encrypted = encrypt_pii_field(card_number)
        record.ghana_card_hash = card_hash
        record.gender = nia_data.get("gender")
        record.nationality = nia_data.get("nationality", "Ghanaian")
        record.region = nia_data.get("region")
        record.ghana_card_status = DocumentStatus(nia_data.get("card_status", "UNKNOWN"))
        record.nia_verified = True
        record.data_sources = list(set((record.data_sources or []) + ["NIA"]))
        record.overall_confidence = 0.99
        record.nia_last_sync_at = datetime.now(timezone.utc)
        record.last_verified_at = datetime.now(timezone.utc)

        if existing is None:
            self._db.add(record)
        await self._db.flush()
        return record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_es_score(score: float, max_score: float) -> float:
    if max_score and max_score > 0:
        return min(1.0, score / max_score)
    return 0.0


def _infer_match_fields(name: str, dob: date | None, source: dict) -> list[str]:
    fields = []
    if source.get("full_name", "").lower() == name.lower():
        fields.append("name_exact")
    else:
        fields.append("name_fuzzy")
    if dob:
        fields.append("dob_exact")
    return fields


def _get_nia_client():
    from ..ghana_card.client import NIAClient
    return NIAClient()


def _get_elasticsearch_client():
    from elasticsearch import AsyncElasticsearch
    from ...shared.config import get_settings
    s = get_settings()
    return AsyncElasticsearch(
        [s.elasticsearch_url],
        api_key=s.elasticsearch_api_key,
        verify_certs=True,
    )
