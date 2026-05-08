"""Basic health and smoke tests for the API Gateway."""
import pytest
from unittest.mock import patch, AsyncMock


def test_settings_loads():
    """Settings object loads without error in test environment."""
    from backend.shared.config import get_settings
    s = get_settings()
    assert s.environment == "development"
    assert s.app_name == "IDIntel Ghana API"


def test_ghana_card_validator_valid():
    from backend.shared.utils.encryption import GhanaCardValidator
    assert GhanaCardValidator.is_valid("GHA-123456789-0")
    assert GhanaCardValidator.normalize("gha-123456789-0") == "GHA-123456789-0"


def test_ghana_card_validator_invalid():
    from backend.shared.utils.encryption import GhanaCardValidator
    assert not GhanaCardValidator.is_valid("GHA-12345-0")
    assert not GhanaCardValidator.is_valid("123456789")
    assert not GhanaCardValidator.is_valid("")


def test_phone_validator_normalize():
    from backend.shared.utils.encryption import PhoneValidator
    assert PhoneValidator.normalize("0244000000") == "+233244000000"
    assert PhoneValidator.normalize("233244000000") == "+233244000000"
    assert PhoneValidator.normalize("+233244000000") == "+233244000000"


def test_phone_validator_ghana():
    from backend.shared.utils.encryption import PhoneValidator
    assert PhoneValidator.is_valid_ghana("0244000000")
    assert PhoneValidator.is_valid_ghana("+233244000000")
    assert not PhoneValidator.is_valid_ghana("+447911123456")


def test_pagination_params():
    from backend.shared.utils.pagination import PaginationParams, PaginatedResponse
    params = PaginationParams(page=2, per_page=10)
    assert params.offset == 10

    result = PaginatedResponse.build(items=list(range(10)), total=25, params=params)
    assert result.total_pages == 3
    assert result.has_next is True
    assert result.has_prev is True


def test_hash_pii_for_audit_deterministic():
    """Same input always produces same hash."""
    with patch.dict("os.environ", {"SECRET_KEY": "a" * 64}):
        from backend.shared.security import hash_pii_for_audit
        h1 = hash_pii_for_audit("GHA-123456789-0")
        h2 = hash_pii_for_audit("GHA-123456789-0")
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex digest

        h3 = hash_pii_for_audit("GHA-000000000-0")
        assert h1 != h3


def test_score_to_band():
    from backend.fraud_detection_service.models.risk_scorer import _score_to_band
    assert _score_to_band(100)[0] == "LOW"
    assert _score_to_band(300)[0] == "MEDIUM"
    assert _score_to_band(600)[0] == "HIGH"
    assert _score_to_band(800)[0] == "CRITICAL"


def test_audit_sign_and_verify():
    from backend.api_gateway._signing import sign_audit_record, verify_audit_record
    record = {"id": "test-123", "institution_id": "inst-001", "timestamp": "2025-01-01T00:00:00Z"}
    sig = sign_audit_record(record)
    assert isinstance(sig, str)
    assert len(sig) == 128  # Ed25519 signature is 64 bytes = 128 hex chars
    assert verify_audit_record(record, sig) is True
    assert verify_audit_record({**record, "institution_id": "tampered"}, sig) is False


@pytest.mark.asyncio
async def test_fastapi_health_endpoint():
    """Health endpoint returns 200 without database."""
    from httpx import AsyncClient, ASGITransport
    with patch("backend.shared.database.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock(return_value=None)
        mock_engine.begin.return_value = mock_conn

        from backend.api_gateway.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
