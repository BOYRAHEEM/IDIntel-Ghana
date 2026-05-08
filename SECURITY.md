# Security Framework — IDIntel Ghana

## Security Classification: RESTRICTED

This document describes the security controls, policies, and practices governing the IDIntel Ghana platform.

---

## 1. Authentication Architecture

### 1.1 Institution Authentication (Machine-to-Machine)

Every institution must authenticate using **all three** of the following:

```
1. TLS Client Certificate (mTLS)
   - Issued by IDIntel Ghana CA
   - 2048-bit RSA minimum, 4096-bit recommended
   - 12-month validity with mandatory renewal
   - Revocable via OCSP/CRL

2. API Key
   - 256-bit cryptographically random
   - Stored as Argon2id hash (never plaintext)
   - Transmitted in X-IDIntel-API-Key header
   - Rotatable on demand, mandatory rotation every 90 days

3. Request Signing
   - HMAC-SHA256 signature of request body + timestamp
   - Prevents replay attacks (5-minute timestamp window)
   - Signature key separate from API key
```

### 1.2 User Authentication (Human Operators)

```
Multi-Factor Authentication (MFA) — Required for ALL users

1. Primary: Username + Password
   - bcrypt hash with cost factor 12
   - Minimum 12 characters, complexity enforced
   - Password history: last 12 passwords blocked
   - Maximum login attempts: 5, then 15-minute lockout

2. Second Factor: TOTP (Google Authenticator / Authy)
   - Or hardware FIDO2/WebAuthn key (preferred for admin roles)

3. Session Token
   - RS256-signed JWT
   - 4-hour expiry
   - Stored in Redis, invalidated on logout or suspicious activity
   - Rotated on privilege escalation
```

---

## 2. Authorization Model

### 2.1 Role Hierarchy

```
PLATFORM_ADMIN (IDIntel staff only)
    │
    ├── INSTITUTION_ADMIN
    │       │
    │       ├── COMPLIANCE_OFFICER
    │       ├── ANALYST
    │       └── API_ONLY_SERVICE_ACCOUNT
    │
    └── AUDITOR (read-only, audit logs only)
```

### 2.2 Role Permissions Matrix

| Action | Platform Admin | Institution Admin | Compliance Officer | Analyst | API Service |
|---|---|---|---|---|---|
| Ghana Card Lookup | ✓ | ✓ | ✓ | ✓ | ✓ |
| Full Intelligence Report | ✓ | ✓ | ✓ | ✓ | ✓ |
| Fraud Risk Score | ✓ | ✓ | ✓ | ✓ | ✓ |
| Relationship Graph | ✓ | ✓ | ✓ | ✗ | by-config |
| Raw Biometric Hash | ✓ | ✗ | ✗ | ✗ | ✗ |
| Audit Log Export | ✓ | own-inst | own-inst | ✗ | ✗ |
| Manage Institution Users | ✓ | own-inst | ✗ | ✗ | ✗ |
| Manage API Keys | ✓ | own-inst | ✗ | ✗ | ✗ |
| Onboard Institution | ✓ | ✗ | ✗ | ✗ | ✗ |
| View All Institutions | ✓ | ✗ | ✗ | ✗ | ✗ |
| Model Configuration | ✓ | ✗ | ✗ | ✗ | ✗ |

### 2.3 Institution-Level Data Scoping

Each institution type has a pre-defined **data scope contract**:

```python
DATA_SCOPE = {
    "BANK": [
        "full_name", "dob", "ghana_card_number", "address",
        "phone_verified", "fraud_risk_score", "credit_trust_index",
        "document_validity", "liveness_score"
    ],
    "LAW_ENFORCEMENT": [
        "full_name", "dob", "ghana_card_number", "photo_reference",
        "address", "phone_numbers", "relationship_graph",
        "travel_history", "investigation_report", "alias_names",
        "known_associates"  # requires court order flag
    ],
    "INSURANCE": [
        "full_name", "dob", "ghana_card_number", "address",
        "fraud_risk_score", "document_validity"
    ],
    "TELECOM": [
        "full_name", "dob", "ghana_card_number",
        "phone_verified", "fraud_risk_score"
    ],
    "IMMIGRATION": [
        "full_name", "dob", "ghana_card_number", "passport_number",
        "travel_history", "nationality", "visa_history",
        "watchlist_status"
    ],
}
```

---

## 3. Data Security

### 3.1 Encryption Standards

```
Data at Rest:
  • Database fields: AES-256-GCM, unique IV per record
  • Encryption keys: AWS KMS CMK (FIPS 140-2 Level 3)
  • Key rotation: Automatic every 90 days
  • Backup encryption: Separate KMS key, separate key rotation schedule

Data in Transit:
  • External: TLS 1.3 only (TLS 1.2 disabled)
  • Internal (service-to-service): mTLS via Istio service mesh
  • Database connections: TLS required, self-signed certs rejected
  • Redis: TLS required
  • S3: HTTPS only, bucket policies enforce encryption

Cryptographic Standards:
  • Asymmetric: RSA-4096 or ECDSA P-384
  • Symmetric: AES-256-GCM
  • Hash: SHA-256 (minimum), SHA-3 for new implementations
  • Password: Argon2id (time_cost=3, memory_cost=65536, parallelism=4)
  • Signing: Ed25519 for audit logs
  • HMAC: HMAC-SHA256 for request signing
```

### 3.2 PII Handling

```
Classification:
  SENSITIVE_PII: ghana_card_number, biometric_hash, photo_reference
  PII: full_name, dob, address, phone_number, email
  QUASI-PII: nationality, gender, region
  NON-PII: fraud_score, verification_status, confidence_score

Storage Rules:
  • SENSITIVE_PII: Encrypted + access logged + never in application logs
  • PII: Encrypted + access logged
  • Logs: PII fields replaced with hash or [REDACTED] automatically
  • AI prompts: PII replaced with anonymized tokens before Claude API call
  • Cache: PII cached maximum 5 minutes, TTL enforced
```

---

## 4. Network Security

### 4.1 Perimeter Security

```
Layer 1: AWS CloudFront + AWS WAF
  • OWASP Core Rule Set (CRS)
  • Custom rules: SQLi patterns, XSS, path traversal
  • Rate limiting at CDN level: 10,000 req/5min per IP
  • Geo-restriction: Ghana and authorized countries only (configurable)
  • Bot detection: AWS Bot Control

Layer 2: AWS Shield Standard (DDoS protection)
  • Layer 3/4 DDoS mitigation
  • Optional: AWS Shield Advanced for critical periods

Layer 3: Application Load Balancer
  • TLS termination with certificate pinning
  • Security headers enforced:
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Content-Security-Policy: enforced
    - Referrer-Policy: no-referrer

Layer 4: VPC Security Groups
  • Minimal ingress rules per service
  • No 0.0.0.0/0 ingress to private subnets
  • Egress: only to required endpoints (NIA, GIS, etc.)

Layer 5: Kubernetes Network Policies (Istio)
  • Default deny all
  • Explicit allow rules per service pair
  • mTLS enforced in STRICT mode for all pods
```

---

## 5. Application Security

### 5.1 Input Validation

All inputs are validated before processing:
- Ghana Card format: regex `GHA-[0-9]{9}-[0-9]` 
- Phone: E.164 format, Ghana country code verified
- Dates: ISO 8601, past dates only for DOB
- Names: Unicode letters only, length limits enforced
- Injection prevention: Parameterized queries everywhere, no raw SQL concatenation
- File uploads: Not supported — API JSON only

### 5.2 Output Security

- Response filtering: Only fields in institution's data scope
- No stack traces in production error responses
- Error messages designed to avoid information leakage
- Consistent timing for authentication failures (prevent timing attacks)

### 5.3 Dependency Security

- Automated dependency scanning: Dependabot + Snyk
- No transitive dependencies with known CVEs (CVSS >= 7.0) in production
- Private PyPI/NPM mirror for supply chain security
- Docker base images: official slim images only, scanned with Trivy

---

## 6. Audit and Monitoring

### 6.1 What Is Logged

Every single request generates:
```
• Who: institution_id + user_id + session_id
• What: endpoint + query type + fields requested
• About whom: subject identity hash (not plaintext)
• When: UTC timestamp with millisecond precision
• Result: status code + verification result
• Context: IP address, user agent, request ID
• Signature: Ed25519 signature of entire record
```

### 6.2 Alerting Rules

| Condition | Alert Level | Response |
|---|---|---|
| Failed auth > 10 in 5min | HIGH | Auto-block IP, notify institution admin |
| Data access outside business hours | MEDIUM | Log + flag for review |
| Bulk lookups > 100 in 1min | HIGH | Rate limit + notify |
| New IP for existing institution | MEDIUM | Log + email alert |
| Fraud score query without purpose code | HIGH | Block request |
| Service error rate > 1% | HIGH | PagerDuty alert |
| Audit log gap detected | CRITICAL | Immediate escalation |
| Unusual country access | CRITICAL | Auto-block + escalation |

---

## 7. Incident Response

### Severity Classification

| Level | Description | Response Time |
|---|---|---|
| P0 — Critical | Data breach suspected, system compromise | 15 minutes |
| P1 — High | Unauthorized access attempt, service down | 1 hour |
| P2 — Medium | Anomalous access patterns, failed attacks | 4 hours |
| P3 — Low | Policy violations, audit anomalies | 24 hours |

### P0 Response Runbook

```
1. Detect (automated alert or manual report)
2. Assess scope — which institutions, which data, what time window
3. Isolate — disable affected institution API keys immediately
4. Notify — NCSC Ghana, affected institutions, legal team
5. Preserve evidence — immutable audit logs, system snapshots
6. Investigate — root cause analysis
7. Remediate — patch + credential rotation
8. Report — post-incident report within 72 hours (Act 843 requirement)
9. Review — security control update
```

---

## 8. Security Testing Requirements

| Test Type | Frequency | Performed By |
|---|---|---|
| Static Application Security Testing (SAST) | Every commit | Automated (Semgrep + Bandit) |
| Dynamic Application Security Testing (DAST) | Weekly | Automated (OWASP ZAP) |
| Software Composition Analysis (SCA) | Every commit | Automated (Snyk) |
| Container Image Scanning | Every build | Automated (Trivy) |
| Internal Penetration Test | Quarterly | Internal security team |
| External Penetration Test | Annually | Certified third party (CREST) |
| Red Team Exercise | Annually | External red team |
| Social Engineering Assessment | Bi-annually | External firm |

---

## 9. Key Management

```
AWS KMS Key Hierarchy:

Root Key (AWS Managed)
    │
    ├── IDIntel-Master-CMK (Customer Managed)
    │       │
    │       ├── Identity-Encryption-Key (auto-rotated 90 days)
    │       ├── Audit-Signing-Key (manual rotation, 365 days)
    │       ├── Report-Encryption-Key (auto-rotated 90 days)
    │       └── Backup-Encryption-Key (auto-rotated 180 days)
    │
    └── IDIntel-HSM-Cluster (CloudHSM for FIPS 140-2 Level 3)
            │
            └── mTLS-CA-Key (never leaves HSM)
```

---

*Security questions: security@idintel.com.gh | Bug bounty: TBD post-launch*
