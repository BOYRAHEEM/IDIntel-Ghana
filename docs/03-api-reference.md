# API Reference — IDIntel Ghana

**Base URL:** `https://api.idintel.com.gh/v1`
**Protocol:** HTTPS + mTLS
**Auth:** API Key + JWT Bearer Token
**Format:** JSON (application/json)
**Versioning:** URI path versioning (`/v1/`, `/v2/`)

---

## Authentication

### Headers Required on Every Request

```http
X-IDIntel-API-Key: idig_live_<your-api-key>
Authorization: Bearer <jwt-token>
X-Request-ID: <client-generated-uuid>
X-Request-Timestamp: <ISO-8601-timestamp>
X-Request-Signature: <HMAC-SHA256 of body+timestamp>
Content-Type: application/json
```

### Obtain JWT Token

```http
POST /v1/auth/token
Content-Type: application/json

{
  "api_key": "idig_live_xxxx",
  "institution_id": "inst-GH-0042"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 14400,
  "scope": "identity:read fraud:read intelligence:read"
}
```

---

## Identity Verification Endpoints

### POST /v1/identity/verify

Verify and retrieve an identity profile.

**Request:**
```json
{
  "query_type": "ghana_card",
  "ghana_card_number": "GHA-123456789-0",
  "purpose_code": "ACCOUNT_OPENING",
  "consent_reference": "CONSENT-2025-01-15-GCB-001",
  "requesting_officer": "usr-CBG-1234",
  "additional_context": {
    "channel": "branch",
    "branch_code": "CBG-ACC-001"
  }
}
```

**Query Types:**
- `ghana_card` — Direct NIA lookup by Ghana Card number
- `name_dob` — Fuzzy name + date of birth search
- `phone_number` — Telecom integration lookup
- `passport` — GIS passport number lookup
- `ssnit` — SSNIT number lookup
- `multi_identifier` — Provide multiple identifiers for highest confidence

**Response (200 OK):**
```json
{
  "request_id": "req-uuid-v4",
  "timestamp": "2025-01-15T10:30:45.123Z",
  "verification_status": "VERIFIED",
  "confidence_score": 0.99,
  "identity_profile": {
    "identity_id": "idig-GH-0000045231",
    "ghana_card_number": "GHA-123456789-0",
    "full_name": "Kwame Asante Mensah",
    "date_of_birth": "1985-03-22",
    "gender": "M",
    "nationality": "Ghanaian",
    "address": {
      "region": "Greater Accra",
      "district": "Accra Metro",
      "town": "East Legon",
      "street": "[AVAILABLE ON REQUEST]"
    },
    "document_status": {
      "ghana_card": "VALID",
      "expiry_date": "2030-03-22",
      "issue_date": "2020-03-22"
    },
    "phone_verified": true,
    "photo_available": true,
    "data_sources": ["NIA", "GIS", "SSNIT"],
    "last_verified": "2025-01-15T10:30:45Z"
  },
  "audit_reference": "aud-uuid-v4"
}
```

**Response Codes:**
- `200 VERIFIED` — Identity confirmed, profile returned
- `200 PARTIAL_MATCH` — Some fields matched, confidence below 90%
- `200 NOT_FOUND` — No matching identity found
- `200 BLOCKED` — Identity flagged; institution must contact compliance
- `400 INVALID_QUERY` — Query parameters invalid
- `403 UNAUTHORIZED_SCOPE` — Institution not authorized for this query type
- `429 RATE_LIMIT_EXCEEDED` — Quota exceeded
- `503 SOURCE_UNAVAILABLE` — NIA API temporarily unavailable

---

### POST /v1/identity/search

Fuzzy search for identities (name + DOB or name alone).

**Request:**
```json
{
  "full_name": "Kwame Mensah",
  "date_of_birth": "1985-03-22",
  "gender": "M",
  "region": "Greater Accra",
  "purpose_code": "FRAUD_INVESTIGATION",
  "max_results": 5,
  "min_confidence": 0.80
}
```

**Response:**
```json
{
  "request_id": "req-uuid",
  "total_candidates": 3,
  "candidates": [
    {
      "identity_id": "idig-GH-0000045231",
      "full_name": "Kwame Asante Mensah",
      "confidence_score": 0.97,
      "match_fields": ["name_exact", "dob_exact", "gender", "region"],
      "ghana_card_status": "VALID"
    }
  ]
}
```

---

### GET /v1/identity/{identity_id}/profile

Retrieve a full identity profile by IDIntel identity ID.

**Response:** Same as verify endpoint profile object.

---

### GET /v1/identity/{identity_id}/usage-history

Retrieve history of which institutions have queried this identity.

**Required Role:** `COMPLIANCE_OFFICER` or `PLATFORM_ADMIN`

**Response:**
```json
{
  "identity_id": "idig-GH-0000045231",
  "query_history": [
    {
      "query_date": "2025-01-10T09:15:00Z",
      "institution_name": "Consolidated Bank Ghana",
      "institution_type": "BANK",
      "purpose_code": "ACCOUNT_OPENING",
      "fields_accessed": ["name", "dob", "ghana_card", "address"],
      "result": "VERIFIED"
    }
  ],
  "total_queries": 1,
  "institutions_queried": 1
}
```

---

## Fraud Detection Endpoints

### POST /v1/fraud/score

Generate a real-time fraud risk score.

**Request:**
```json
{
  "identity_id": "idig-GH-0000045231",
  "context": {
    "transaction_type": "account_opening",
    "channel": "digital",
    "device_fingerprint_hash": "sha256-of-device-fp",
    "ip_address_hash": "sha256-of-ip",
    "location_region": "Greater Accra",
    "query_velocity_window_minutes": 60
  },
  "purpose_code": "KYC_REFRESH"
}
```

**Response:**
```json
{
  "request_id": "req-uuid",
  "identity_id": "idig-GH-0000045231",
  "fraud_score": {
    "overall_score": 145,
    "score_band": "LOW",
    "score_interpretation": "Low risk. No significant fraud indicators detected.",
    "contributing_factors": [
      {
        "factor": "identity_freshness",
        "weight": 0.15,
        "value": "GOOD",
        "explanation": "Ghana Card issued 5+ years ago, no recent suspicious activity"
      },
      {
        "factor": "cross_institution_velocity",
        "weight": 0.05,
        "value": "NORMAL",
        "explanation": "1 query in last 30 days — within normal range"
      },
      {
        "factor": "document_consistency",
        "weight": 0.10,
        "value": "HIGH",
        "explanation": "Name, DOB, address consistent across all sources"
      }
    ],
    "watchlist_status": "CLEAR",
    "sanctions_status": "CLEAR",
    "model_version": "fraud-v3.2.1",
    "score_timestamp": "2025-01-15T10:30:45Z"
  },
  "recommended_action": "PROCEED",
  "audit_reference": "aud-uuid"
}
```

**Score Bands:**

| Score Range | Band | Recommended Action |
|---|---|---|
| 0–200 | LOW | Proceed normally |
| 201–500 | MEDIUM | Additional verification recommended |
| 501–750 | HIGH | Manual review required before proceeding |
| 751–1000 | CRITICAL | Decline + flag for investigation |

---

### POST /v1/fraud/analyze-pattern

Detect fraud patterns across multiple related identities.

**Request:**
```json
{
  "identity_ids": ["idig-GH-0000045231", "idig-GH-0000045299"],
  "analysis_type": "network_fraud_ring",
  "time_window_days": 90,
  "purpose_code": "FRAUD_INVESTIGATION"
}
```

---

## AI Intelligence Endpoints

### POST /v1/intelligence/summary

Generate an AI-powered intelligence summary for an identity.

**Request:**
```json
{
  "identity_id": "idig-GH-0000045231",
  "report_type": "QUICK_SUMMARY",
  "include_sections": [
    "identity_overview",
    "risk_assessment",
    "institutional_history",
    "behavioral_notes"
  ],
  "purpose_code": "KYC_REFRESH",
  "language": "en",
  "format": "json"
}
```

**Report Types:**
- `QUICK_SUMMARY` — 1-page summary (60-second generation)
- `FULL_INTELLIGENCE_DOSSIER` — Comprehensive report (2-3 minute generation)
- `FRAUD_INVESTIGATION_REPORT` — Investigation-focused with network analysis
- `COMPLIANCE_CERTIFICATE` — Regulatory compliance documentation
- `BEHAVIORAL_ANOMALY_REPORT` — Focus on behavioral deviations

**Response:**
```json
{
  "request_id": "req-uuid",
  "report_id": "rpt-uuid",
  "identity_id": "idig-GH-0000045231",
  "report_type": "QUICK_SUMMARY",
  "generated_at": "2025-01-15T10:31:05Z",
  "report": {
    "identity_overview": {
      "summary": "Kwame Asante Mensah is a verified Ghanaian citizen with a valid Ghana Card (GHA-123456789-0) issued in 2020. Identity records are consistent across NIA, SSNIT, and Ghana Immigration Service databases. No adverse flags detected.",
      "confidence": "HIGH",
      "sources_verified": 3
    },
    "risk_assessment": {
      "summary": "Risk profile is LOW. Fraud score: 145/1000. No active watchlist flags, no sanctions matches. Document consistency is 100% across verified sources. One prior institutional query in the last 90 days (Consolidated Bank Ghana, account opening).",
      "fraud_score": 145,
      "risk_band": "LOW"
    },
    "institutional_history": {
      "summary": "Subject has verified relationships with one licensed financial institution in the past 90 days. Normal verification activity consistent with retail banking profile.",
      "institution_count": 1
    },
    "behavioral_notes": {
      "summary": "No anomalous query velocity patterns detected. Identity usage consistent with a low-activity individual. No geographic inconsistencies.",
      "anomalies_detected": 0
    }
  },
  "report_pdf_url": "https://api.idintel.com.gh/v1/reports/rpt-uuid/download",
  "report_expires_at": "2025-04-15T10:31:05Z",
  "audit_reference": "aud-uuid",
  "ai_model_used": "claude-sonnet-4-6",
  "disclaimer": "This report is generated by AI and is for authorized institutional use only. All decisions should include human judgment."
}
```

---

### POST /v1/intelligence/investigation-report

Generate a comprehensive investigation dossier (law enforcement / compliance).

**Required Role:** `ANALYST` or above. Law enforcement use requires `LAW_ENFORCEMENT` institution type.

**Request:**
```json
{
  "subject_identity_id": "idig-GH-0000045231",
  "investigation_reference": "CID-INV-2025-001234",
  "investigating_officer": "usr-GHPOL-0099",
  "include_network_map": true,
  "network_depth": 2,
  "time_window_days": 365,
  "purpose_code": "LAW_ENFORCEMENT_QUERY",
  "legal_authority": "COURT_ORDER",
  "court_order_reference": "HC/CR/001/2025"
}
```

---

## Relationship Mapping Endpoints

### GET /v1/identity/{identity_id}/relationships

Retrieve the relationship graph for an identity.

**Query Parameters:**
- `depth` (int, 1-3): Graph traversal depth
- `relationship_types` (array): Filter by type (financial, family, associate, shared_device)
- `min_confidence` (float): Minimum relationship confidence

**Response:**
```json
{
  "identity_id": "idig-GH-0000045231",
  "graph": {
    "nodes": [
      {
        "id": "idig-GH-0000045231",
        "type": "SUBJECT",
        "name": "Kwame Asante Mensah",
        "risk_score": 145
      },
      {
        "id": "idig-GH-0000055123",
        "type": "ASSOCIATE",
        "name": "[REDACTED — request full access]",
        "risk_score": 680,
        "relationship_to_subject": "shared_phone_number",
        "confidence": 0.94
      }
    ],
    "edges": [
      {
        "source": "idig-GH-0000045231",
        "target": "idig-GH-0000055123",
        "relationship_type": "shared_phone_number",
        "confidence": 0.94,
        "first_seen": "2024-06-01",
        "last_seen": "2025-01-10"
      }
    ]
  }
}
```

---

## Audit and Compliance Endpoints

### GET /v1/audit/logs

Retrieve audit logs for the institution.

**Query Parameters:**
- `start_date`, `end_date` (ISO 8601)
- `user_id` (filter by user)
- `query_type` (filter by type)
- `page`, `per_page`

### POST /v1/audit/export

Export audit logs in compliance report format.

```json
{
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "format": "PDF",
  "include_signature_chain": true
}
```

---

## Error Response Format

All errors follow RFC 7807 (Problem Details):

```json
{
  "type": "https://api.idintel.com.gh/errors/rate-limit-exceeded",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "You have exceeded your per-minute quota of 100 requests. Reset in 45 seconds.",
  "instance": "/v1/identity/verify",
  "retry_after": 45,
  "request_id": "req-uuid",
  "timestamp": "2025-01-15T10:30:45Z"
}
```

---

## Rate Limits

| Institution Tier | Per Minute | Per Hour | Per Day |
|---|---|---|---|
| Starter | 20 | 500 | 5,000 |
| Professional | 100 | 3,000 | 50,000 |
| Enterprise | 500 | 15,000 | 200,000 |
| Government | 1,000 | 50,000 | Unlimited |

Rate limit headers on every response:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705312245
X-RateLimit-Window: 60
```
