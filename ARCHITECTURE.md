# System Architecture — IDIntel Ghana

## 1. Architectural Principles

| Principle | Implementation |
|---|---|
| **Zero Trust** | Every request is authenticated and authorized regardless of origin |
| **Defense in Depth** | Multiple independent security layers — network, application, data |
| **Least Privilege** | Each service and user has the minimum permissions required |
| **Immutability** | Audit logs are append-only and cryptographically signed |
| **Data Minimization** | Return only fields authorized for the requesting institution |
| **Privacy by Design** | PII is encrypted at field level before storage |
| **Observability** | Every request, decision, and data access is logged and traceable |
| **API-First** | All functionality exposed via versioned, documented REST APIs |

---

## 2. Microservices Architecture

### 2.1 API Gateway Service

**Responsibility:** Single entry point for all external traffic.

```
Incoming Request
      │
      ▼
[AWS WAF] ──── (Block known threats, SQLi, XSS)
      │
      ▼
[Nginx / Load Balancer] ──── (SSL termination, DDoS mitigation)
      │
      ▼
[FastAPI Gateway App]
      ├── [IP Allowlist Check]
      ├── [API Key Validation] ──── (Vault lookup)
      ├── [mTLS Certificate Verification]
      ├── [JWT Token Validation]
      ├── [Rate Limit Check] ──── (Redis sliding window)
      ├── [Institution Quota Check]
      ├── [RBAC Permission Check]
      ├── [Request Sanitization]
      ├── [Audit Pre-Log] ──── (Immutable log of incoming request)
      └── [Route to Appropriate Microservice]
```

**Key Features:**
- Mutual TLS enforcement
- Per-institution rate limiting (requests/minute and requests/day)
- Request/response schema validation
- Automatic API key rotation support
- Canary routing for gradual rollouts

---

### 2.2 Identity Service

**Responsibility:** Resolve, merge, and return verified identity profiles.

```
Identity Query
      │
      ▼
[Query Parser] ──── (Ghana Card #, Name+DOB, Phone, Passport)
      │
      ▼
[Identity Resolver]
      ├── [Ghana Card / NIA Lookup] ──── (Secure proxy to NIA API)
      ├── [Elasticsearch Fuzzy Search] ──── (Name matching, alias detection)
      ├── [Phone Number Lookup] ──── (Telecom partner integration)
      ├── [Passport Lookup] ──── (GIS integration)
      └── [Institutional Record Aggregator] ──── (Bank, Insurance, etc.)
      │
      ▼
[Profile Builder]
      ├── [Record Deduplication] ──── (ML-based entity resolution)
      ├── [Confidence Scoring] ──── (Per-field confidence %)
      └── [Field-Level Authorization Filter] ──── (Per-institution data mask)
      │
      ▼
[Verified Identity Profile]
```

**Data Sources Integrated:**
- NIA / Ghana Card (primary authoritative source)
- Ghana Immigration Service (GIS)
- Driver and Vehicle Licensing Authority (DVLA)
- Social Security and National Insurance Trust (SSNIT)
- Ghana Revenue Authority (GRA)
- Bank of Ghana licensed institutions (via consent framework)
- NCA-registered telecom operators

---

### 2.3 AI Intelligence Service

**Responsibility:** Generate natural language intelligence summaries and investigation reports using Claude AI.

```
Intelligence Request
      │
      ▼
[Context Assembler]
      ├── [Identity Profile]
      ├── [Risk Score]
      ├── [Relationship Graph]
      ├── [Historical Activity]
      └── [Flagged Incidents]
      │
      ▼
[Prompt Engine] ──── (Template selection by report type)
      │
      ▼
[Claude claude-sonnet-4-6 API] ──── (Anthropic — with prompt caching)
      │
      ▼
[Report Post-Processor]
      ├── [PII Redaction Check]
      ├── [Confidence Annotation]
      ├── [Source Citation]
      └── [PDF/JSON Export]
      │
      ▼
[Intelligence Report]
```

**Report Types:**
- Quick Verification Summary
- Full Identity Intelligence Dossier
- Fraud Investigation Report
- Relationship Network Analysis Report
- Behavioral Anomaly Report
- Regulatory Compliance Certificate

---

### 2.4 Fraud Detection Service

**Responsibility:** Real-time and batch ML-based fraud risk scoring.

```
Fraud Score Request
      │
      ▼
[Feature Extractor]
      ├── [Identity Freshness] ──── (How recently verified/created)
      ├── [Cross-Institution Activity] ──── (Simultaneous applications)
      ├── [Document Consistency] ──── (Cross-source field matching)
      ├── [Velocity Signals] ──── (Lookup frequency, location patterns)
      ├── [Network Risk] ──── (Risk from connected identities)
      ├── [Behavioral Baseline] ──── (Deviation from established patterns)
      └── [Sanctions / Watchlist] ──── (Interpol, OFAC, local lists)
      │
      ▼
[XGBoost Risk Model] + [Isolation Forest Anomaly Model]
      │
      ▼
[Risk Score Engine]
      ├── [Score: 0-1000]
      ├── [Risk Band: LOW / MEDIUM / HIGH / CRITICAL]
      ├── [Contributing Factors (SHAP values)]
      └── [Recommended Actions]
      │
      ▼
[Fraud Risk Response]
```

---

### 2.5 Audit Service

**Responsibility:** Immutable, cryptographically verified audit trail for all platform activity.

Every data access event generates an immutable audit record:
```json
{
  "event_id": "uuid-v4",
  "timestamp": "ISO-8601",
  "institution_id": "inst-GH-0042",
  "institution_name": "Consolidated Bank Ghana",
  "user_id": "usr-CBG-1234",
  "user_role": "kyc_officer",
  "query_type": "ghana_card_lookup",
  "query_params_hash": "sha256-of-params",
  "subject_id_hash": "sha256-of-subject-id",
  "fields_accessed": ["name", "dob", "photo_ref", "address"],
  "response_status": "verified",
  "purpose_code": "account_opening",
  "legal_basis": "consent_v2_signed_2025-01-15",
  "data_retention_days": 90,
  "request_ip": "196.201.x.x",
  "session_id": "sess-uuid",
  "signature": "ed25519-signature-of-record",
  "previous_hash": "sha256-of-previous-record"
}
```

Audit records are:
- Stored in an append-only PostgreSQL partition
- Replicated to AWS S3 Glacier for 7-year retention
- Signed with Ed25519 per record and chained (blockchain-style hash chain)
- Exported to institution compliance officers on demand
- Indexed in Elasticsearch for SIEM integration

---

## 3. Data Architecture

### 3.1 Database Strategy

```
┌─────────────────────────────────────────────────────────┐
│                  PostgreSQL Primary (AWS RDS)            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Identities  │  │ Institutions │  │ Audit Logs   │  │
│  │  (encrypted) │  │    & Users   │  │  (WORM)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Fraud Scores │  │ Risk Events  │  │  API Keys    │  │
│  │   History    │  │   & Alerts   │  │  (hashed)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               Elasticsearch (Search Cluster)             │
│    Identity search index (fuzzy, phonetic matching)      │
│    Full-text investigation search                        │
│    Audit event indexing (SIEM)                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   Redis Cluster (Cache)                   │
│    Session tokens (TTL: 4h)                              │
│    Rate limit counters (sliding window)                  │
│    Institution quota state                               │
│    Frequently accessed identity cache (TTL: 5min)        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                 Neo4j Graph Database                      │
│    Identity relationship graphs                          │
│    Network fraud ring detection                          │
│    Connected institution records                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               AWS S3 (Encrypted Object Storage)          │
│    Generated PDF reports                                 │
│    Exported compliance reports                           │
│    ML model artifacts                                    │
│    Audit log archives (Glacier)                          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Encryption Strategy

| Data State | Method |
|---|---|
| Data at Rest (DB) | AES-256-GCM field-level encryption, keys in AWS KMS |
| Data in Transit | TLS 1.3 minimum, mTLS for service-to-service |
| Backup Encryption | AES-256 with separate backup KMS key |
| API Keys (stored) | Argon2id hash, never stored in plaintext |
| JWT Tokens | RS256 signed, 1-hour expiry |
| Audit Logs | Ed25519 per-record signatures |
| PII Fields | Encrypted with per-institution derived keys |

---

## 4. Network Architecture (AWS)

```
Internet
   │
   ▼
[AWS CloudFront + WAF]
   │
   ▼
[Public ALB] (HTTPS only, TLS 1.3)
   │
   ▼
[VPC: 10.0.0.0/16]
   ├── Public Subnets (10.0.0.0/20) ──── NAT Gateway, Bastion Host
   ├── Private App Subnets (10.0.16.0/20) ──── EKS Node Groups
   └── Private Data Subnets (10.0.32.0/20) ──── RDS, ElastiCache, MSK
         │
         ▼
   [AWS PrivateLink] ──── NIA Integration (Dedicated Private Link)
   [AWS PrivateLink] ──── GIS Integration
   [AWS Direct Connect] ──── Government Data Center (optional)
```

**Security Groups:**
- API Gateway SG: Allow 443 from 0.0.0.0/0 (WAF filtered)
- App Services SG: Allow only from API Gateway SG
- Database SG: Allow only from App Services SG on specific ports
- Audit SG: Append-only — no DELETE, UPDATE permissions at DB level

---

## 5. Identity Matching Algorithm

```
Input: {ghana_card_number?, full_name?, dob?, phone?, passport_number?}
  │
  ▼
[Confidence Router]
  ├── If ghana_card_number: Direct NIA lookup (confidence: 99%+)
  ├── If passport_number: GIS lookup (confidence: 97%+)
  ├── If name + dob: Elasticsearch phonetic + exact match (confidence: 70-95%)
  └── If phone: Telecom integration lookup (confidence: 85-92%)
  │
  ▼
[Multi-Source Merge]
  ├── Primary key: Ghana Card Number (if available)
  ├── Secondary keys: Passport, SSNIT, DL Number
  ├── Fuzzy match threshold: Jaro-Winkler > 0.92 for names
  └── DOB tolerance: Exact match required
  │
  ▼
[Deduplication]
  ├── ML entity resolution model
  ├── Blocking on DOB + first 3 chars of surname
  └── Candidate pair scoring → merge if score > 0.85
  │
  ▼
[Verified Profile] with per-field confidence scores
```

---

## 6. Scalability Design

| Component | Scaling Strategy | Target |
|---|---|---|
| API Gateway | Horizontal pod autoscaling (HPA) | 10,000 req/min |
| Identity Service | HPA based on CPU + request queue depth | 5,000 lookups/min |
| AI Intelligence | Queue-based workers (Celery) | 200 reports/min |
| Fraud Detection | HPA, ML inference cached 5min | 8,000 scores/min |
| PostgreSQL | Read replicas + connection pooling (PgBouncer) | 50,000 QPS read |
| Elasticsearch | 3-node cluster, 1 shard per index | Sub-100ms search |
| Redis | Redis Cluster mode, 3 primaries | 100,000 ops/sec |

---

## 7. Disaster Recovery

| Scenario | RTO | RPO | Strategy |
|---|---|---|---|
| Single service failure | 30 sec | 0 | Kubernetes pod restart + health checks |
| AZ failure | 2 min | 0 | Multi-AZ deployment, ALB failover |
| Database failure | 5 min | 5 min | RDS Multi-AZ automatic failover |
| Region failure | 30 min | 15 min | Cross-region RDS read replica promotion |
| Data corruption | 1 hour | 24 hours | Point-in-time recovery (PITR) |
| Full platform rebuild | 4 hours | 24 hours | Terraform IaC full rebuild |

---

*This architecture is designed to meet Ghana government security classification: RESTRICTED.*
