"""Secure client for NIA / Ghana Card API integration.

All communication uses mutual TLS with NIA-issued client certificates.
This client wraps the NIA secure API proxy endpoint.
"""
from __future__ import annotations

import httpx

from ...shared.config import get_settings

settings = get_settings()

NIA_ENDPOINTS = {
    "ghana_card_lookup": "/api/v1/verify/ghana-card",
    "name_dob_search": "/api/v1/search/name-dob",
    "biometric_verify": "/api/v1/verify/biometric",
}


class NIAClient:
    """
    Client for the NIA secure API. Uses mTLS for authentication.
    All NIA API calls are logged in the audit trail before and after.
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.nia_api_base_url,
                cert=(
                    settings.nia_api_client_cert_path,
                    settings.nia_api_client_key_path,
                ),
                verify=settings.nia_api_ca_cert_path,
                timeout=settings.nia_api_timeout_seconds,
                headers={
                    "User-Agent": "IDIntel-Ghana/1.0",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def lookup_by_ghana_card(self, card_number: str) -> dict | None:
        """Look up a Ghana Card from NIA. Returns None if not found or NIA unavailable."""
        try:
            client = self._get_client()
            response = await client.post(
                NIA_ENDPOINTS["ghana_card_lookup"],
                json={"ghana_card_number": card_number},
            )

            if response.status_code == 404:
                return None
            if response.status_code == 503:
                raise NIAUnavailableError("NIA API is temporarily unavailable")

            response.raise_for_status()
            return _parse_nia_response(response.json())

        except httpx.TimeoutException:
            raise NIAUnavailableError("NIA API request timed out")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise NIAUnavailableError(f"NIA API error: {exc.response.status_code}")

    async def lookup_by_name_dob(
        self, full_name: str, date_of_birth: str, gender: str | None = None
    ) -> list[dict]:
        """Fuzzy name + DOB search against NIA."""
        try:
            client = self._get_client()
            payload: dict = {"full_name": full_name, "date_of_birth": date_of_birth}
            if gender:
                payload["gender"] = gender

            response = await client.post(
                NIA_ENDPOINTS["name_dob_search"],
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return [_parse_nia_response(r) for r in data.get("results", [])]

        except httpx.TimeoutException:
            raise NIAUnavailableError("NIA API request timed out")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


def _parse_nia_response(data: dict) -> dict:
    """Normalize NIA API response to internal format."""
    return {
        "full_name": f"{data.get('surname', '')} {data.get('other_names', '')}".strip(),
        "date_of_birth": data.get("date_of_birth"),
        "gender": data.get("gender", "")[:1].upper() or None,
        "nationality": data.get("nationality", "Ghanaian"),
        "region": data.get("region_of_residence"),
        "district": data.get("district"),
        "card_status": _map_nia_status(data.get("card_status", "")),
        "card_issue_date": data.get("issue_date"),
        "card_expiry_date": data.get("expiry_date"),
        "photo_reference_id": data.get("photo_id"),
        "nia_reference": data.get("reference_id"),
        "is_deceased": data.get("is_deceased", False),
    }


def _map_nia_status(nia_status: str) -> str:
    mapping = {
        "ACTIVE": "VALID",
        "VALID": "VALID",
        "EXPIRED": "EXPIRED",
        "SUSPENDED": "SUSPENDED",
        "CANCELLED": "CANCELLED",
        "REVOKED": "CANCELLED",
    }
    return mapping.get(nia_status.upper(), "UNKNOWN")


class NIAUnavailableError(Exception):
    """Raised when the NIA API cannot be reached or returns a server error."""
