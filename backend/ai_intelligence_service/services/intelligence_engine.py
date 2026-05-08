"""AI Intelligence Engine — generates reports using Claude claude-sonnet-4-6.

PII is anonymized before any call to the Anthropic API.
Token maps are stored locally and re-inserted after generation.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.config import get_settings
from ...shared.models.identity import FraudScoreRecord, IdentityRecord
from ...shared.utils.encryption import decrypt_pii_field
from ..prompts.intelligence_prompts import (
    INVESTIGATION_REPORT_PROMPT,
    QUICK_SUMMARY_PROMPT,
    SYSTEM_PROMPT,
)

settings = get_settings()

_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


@dataclass
class ReportResult:
    sections: dict
    model_used: str
    tokens_used: int = 0
    cache_hit: bool = False


class IntelligenceEngine:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def generate_summary(
        self,
        identity_id: str,
        report_type: str,
        sections: list[str],
        purpose_code: str,
        language: str,
        institution: dict,
    ) -> ReportResult:
        identity, fraud_score = await self._load_identity_context(identity_id)
        if identity is None:
            return ReportResult(sections={"error": "Identity not found"}, model_used=settings.anthropic_model)

        anonymized, token_map = _anonymize_identity(identity, fraud_score)
        prompt = QUICK_SUMMARY_PROMPT.format(
            anonymized_data=_format_anonymized_data(anonymized),
            sections=", ".join(sections),
            institution_type=institution.get("institution_type", "INSTITUTION"),
        )

        response_text, tokens_used, cache_hit = await self._call_claude(prompt)
        report_sections = _parse_report_sections(response_text, token_map, sections)

        return ReportResult(
            sections=report_sections,
            model_used=settings.anthropic_model,
            tokens_used=tokens_used,
            cache_hit=cache_hit,
        )

    async def generate_investigation_report(
        self,
        subject_identity_id: str,
        investigation_reference: str,
        investigating_officer: str,
        include_network_map: bool,
        network_depth: int,
        time_window_days: int,
        legal_authority: str,
        court_order_reference: str | None,
        institution: dict,
    ) -> ReportResult:
        identity, fraud_score = await self._load_identity_context(subject_identity_id)
        if identity is None:
            return ReportResult(sections={"error": "Identity not found"}, model_used=settings.anthropic_model)

        anonymized, token_map = _anonymize_identity(identity, fraud_score)
        network_summary = await self._build_network_summary(
            subject_identity_id, network_depth, time_window_days
        ) if include_network_map else {}

        prompt = INVESTIGATION_REPORT_PROMPT.format(
            anonymized_data=_format_anonymized_data(anonymized),
            network_summary=str(network_summary),
            investigation_reference=investigation_reference,
            time_window_days=time_window_days,
            legal_authority=legal_authority,
        )

        response_text, tokens_used, cache_hit = await self._call_claude(prompt)
        report_sections = _parse_report_sections(response_text, token_map, [
            "subject_overview", "timeline", "network_analysis",
            "behavioral_analysis", "risk_assessment", "intelligence_gaps"
        ])

        return ReportResult(
            sections=report_sections,
            model_used=settings.anthropic_model,
            tokens_used=tokens_used,
            cache_hit=cache_hit,
        )

    async def _call_claude(self, user_prompt: str) -> tuple[str, int, bool]:
        """Call Claude with prompt caching on the system prompt."""
        client = _get_client()
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else ""
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        cache_hit = response.usage.cache_read_input_tokens > 0 if hasattr(response.usage, "cache_read_input_tokens") else False

        return content, tokens_used, cache_hit

    async def _load_identity_context(
        self, identity_id: str
    ) -> tuple[IdentityRecord | None, FraudScoreRecord | None]:
        result = await self._db.execute(
            select(IdentityRecord).where(IdentityRecord.idintel_id == identity_id)
        )
        identity = result.scalar_one_or_none()
        if identity is None:
            return None, None

        fraud_result = await self._db.execute(
            select(FraudScoreRecord)
            .where(FraudScoreRecord.identity_id == identity.id)
            .order_by(FraudScoreRecord.created_at.desc())
            .limit(1)
        )
        fraud_score = fraud_result.scalar_one_or_none()
        return identity, fraud_score

    async def _build_network_summary(
        self, identity_id: str, depth: int, window_days: int
    ) -> dict:
        """Build a summary of the identity's relationship network for the AI prompt."""
        return {
            "note": "Network analysis requires Neo4j integration",
            "identity_id": identity_id,
            "depth": depth,
        }


# ---------------------------------------------------------------------------
# Anonymization
# ---------------------------------------------------------------------------

def _anonymize_identity(
    identity: IdentityRecord,
    fraud_score: FraudScoreRecord | None,
) -> tuple[dict, dict]:
    """Replace all PII with tokens. Returns (anonymized_dict, token_map)."""
    token_map = {}

    full_name = decrypt_pii_field(identity.full_name_encrypted) or ""
    person_token = _make_token("PERSON")
    token_map[person_token] = full_name

    anonymized = {
        "person": person_token,
        "age_band": _dob_to_age_band(decrypt_pii_field(identity.date_of_birth_encrypted)),
        "gender": identity.gender,
        "nationality": identity.nationality,
        "region": identity.region,
        "ghana_card_status": identity.ghana_card_status.value if identity.ghana_card_status else "UNKNOWN",
        "data_sources_count": len(identity.data_sources),
        "data_sources": identity.data_sources,
        "overall_confidence": identity.overall_confidence,
        "nia_verified": identity.nia_verified,
        "is_deceased": identity.is_deceased,
        "is_blocked": identity.is_blocked,
        "last_verified": identity.last_verified_at.isoformat() if identity.last_verified_at else "NEVER",
    }

    if fraud_score:
        anonymized["fraud_score"] = fraud_score.overall_score
        anonymized["risk_band"] = fraud_score.risk_band
        anonymized["watchlist_status"] = fraud_score.watchlist_status
        anonymized["sanctions_status"] = fraud_score.sanctions_status
    else:
        anonymized["fraud_score"] = "NOT_SCORED"
        anonymized["risk_band"] = "UNKNOWN"

    return anonymized, token_map


def _make_token(prefix: str) -> str:
    return f"[{prefix}_{secrets.token_hex(4).upper()}]"


def _dob_to_age_band(dob_str: str | None) -> str:
    if not dob_str:
        return "UNKNOWN"
    try:
        from datetime import date
        dob = date.fromisoformat(dob_str)
        age = (date.today() - dob).days // 365
        if age < 18:
            return "UNDER_18"
        if age < 25:
            return "18-24"
        if age < 35:
            return "25-34"
        if age < 45:
            return "35-44"
        if age < 55:
            return "45-54"
        if age < 65:
            return "55-64"
        return "65+"
    except Exception:
        return "UNKNOWN"


def _format_anonymized_data(data: dict) -> str:
    lines = []
    for key, value in data.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _parse_report_sections(
    raw_text: str, token_map: dict, expected_sections: list[str]
) -> dict:
    """Parse Claude's text output into structured sections and re-insert PII tokens."""
    # Re-insert PII tokens into the response
    output_text = raw_text
    for token, real_value in token_map.items():
        output_text = output_text.replace(token, real_value)

    sections = {}
    current_section = "overview"
    current_lines: list[str] = []

    for line in output_text.split("\n"):
        # Detect section headers (numbered or ALL_CAPS)
        header_match = re.match(r"^[\d]+\.\s+([A-Z_]+)[:.]?\s*(.*)", line.strip())
        if header_match:
            if current_lines:
                sections[current_section] = {"summary": " ".join(current_lines).strip()}
            current_section = header_match.group(1).lower()
            current_lines = [header_match.group(2)] if header_match.group(2) else []
        else:
            if line.strip():
                current_lines.append(line.strip())

    if current_lines:
        sections[current_section] = {"summary": " ".join(current_lines).strip()}

    return sections
