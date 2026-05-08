# AI & ML Pipeline — IDIntel Ghana

## Overview

IDIntel Ghana uses two AI/ML subsystems:

1. **Claude AI (Anthropic)** — Natural language intelligence report generation
2. **Custom ML Models** — Quantitative fraud risk scoring and anomaly detection

---

## 1. Claude AI Intelligence Engine

### 1.1 Architecture

```
Identity Data + Risk Scores + History
              │
              ▼
    [PII Anonymizer / Tokenizer]
              │  (No raw PII leaves the system)
              ▼
    [Prompt Template Engine]
              │
              ▼
    [Claude claude-sonnet-4-6 API]
     - Prompt caching for efficiency
     - Streaming for real-time generation
     - Max tokens: 4096 per report section
              │
              ▼
    [Response Post-Processor]
     - PII token re-insertion
     - Confidence annotation
     - Source citation injection
     - Output validation
              │
              ▼
    [Structured Intelligence Report]
```

### 1.2 PII Anonymization Before AI Processing

**Critical security requirement:** No personally identifiable information is sent to the Claude API in raw form.

```python
# Anonymization process
BEFORE (internal):
  {"name": "Kwame Asante Mensah", "dob": "1985-03-22", "card": "GHA-123456789-0"}

AFTER (sent to Claude):
  {"name": "[PERSON_A]", "dob": "[DOB_A]", "card": "[ID_A]", "age_band": "35-45"}

# Token mapping stored locally, never transmitted
TOKEN_MAP = {
  "[PERSON_A]": "Kwame Asante Mensah",
  "[DOB_A]": "1985-03-22",
  "[ID_A]": "GHA-123456789-0"
}
```

### 1.3 Prompt Templates

**Quick Summary Prompt:**
```
You are an identity intelligence analyst for an authorized Ghanaian regulatory institution.
Analyze the following anonymized identity profile and generate a concise verification summary.

Identity Data:
- Person: [PERSON_A]
- Age Band: 35-45 years
- Document Status: VALID (issued 5 years ago)
- Verification Sources: 3 official sources (all consistent)
- Cross-Source Consistency: 100%
- Prior Institutional Queries (90 days): 1 (financial institution, account opening)
- Watchlist Status: CLEAR
- Sanctions Status: CLEAR
- Fraud Risk Score: 145/1000 (LOW band)
- Behavioral Anomalies: None detected

Generate:
1. IDENTITY_OVERVIEW (2-3 sentences): Verification status and document validity
2. RISK_ASSESSMENT (2-3 sentences): Risk score interpretation and key factors
3. INSTITUTIONAL_HISTORY (1-2 sentences): Recent institutional activity pattern
4. BEHAVIORAL_NOTES (1-2 sentences): Any notable behavioral observations
5. ANALYST_RECOMMENDATION (1 sentence): Proceed / Review / Escalate

Be factual, concise, and professional. Do not speculate beyond the data provided.
```

**Investigation Report Prompt:**
```
You are a senior intelligence analyst generating a formal investigation dossier for
law enforcement use. Apply analytical rigor and clearly distinguish between confirmed
facts and inferred patterns.

[Detailed structured data provided here...]

Generate a formal investigation report including:
1. Subject Overview and Identity Verification Status
2. Timeline Reconstruction (chronological activity summary)
3. Network Analysis (known associates and relationship risk)
4. Behavioral Pattern Analysis
5. Financial Activity Indicators (if available)
6. Fraud Risk Assessment and Contributing Factors
7. Intelligence Gaps and Recommended Follow-up Actions
8. Analyst Confidence Assessment

Format: Professional law enforcement intelligence report style.
Clearly label: [CONFIRMED], [PROBABLE], [POSSIBLE] for each key finding.
```

### 1.4 Prompt Caching Strategy

Claude API prompt caching reduces costs by ~80% for repeated report structures:

```python
# Cached portions (system prompt + template = ~2000 tokens, cached)
# Variable portion (identity data = ~500 tokens, not cached)

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT_AND_TEMPLATE,  # Static — cached
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": anonymized_identity_data  # Dynamic — not cached
            }
        ]
    }
]
```

---

## 2. Fraud Detection ML Models

### 2.1 Model Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Fraud Detection Pipeline                    │
│                                                             │
│  Raw Input Features (40+ features)                          │
│         │                                                   │
│         ▼                                                   │
│  [Feature Extractor + Normalizer]                           │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐    ┌──────────────────┐                   │
│  │  XGBoost    │    │ Isolation Forest │                   │
│  │  Classifier │    │ Anomaly Detector │                   │
│  │  (fraud     │    │ (behavioral      │                   │
│  │   patterns) │    │  anomalies)      │                   │
│  └──────┬──────┘    └────────┬─────────┘                   │
│         │                   │                              │
│         ▼                   ▼                              │
│    [Score Ensemble + SHAP Explainer]                        │
│         │                                                   │
│         ▼                                                   │
│    [Final Risk Score 0-1000 + Explanation]                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Feature Set (40+ Features)

**Identity Document Features:**
- `card_age_days` — Days since Ghana Card issuance
- `card_status_encoded` — VALID/EXPIRED/SUSPENDED
- `address_change_count_90d` — Address updates in 90 days
- `dob_card_consistency` — DOB matches across all sources
- `name_consistency_score` — Name consistency across sources (0-1)
- `photo_match_available` — Whether photo reference exists

**Behavioral / Velocity Features:**
- `query_count_1h` — Queries in last 1 hour
- `query_count_24h` — Queries in last 24 hours
- `query_count_30d` — Queries in last 30 days
- `unique_institutions_30d` — Distinct institutions querying in 30 days
- `simultaneous_applications_flag` — Multiple financial applications at same time
- `night_query_ratio` — Proportion of queries during 23:00-05:00
- `weekend_query_ratio` — Weekend query proportion

**Network / Relationship Features:**
- `high_risk_associate_count` — Known associates with HIGH/CRITICAL risk score
- `fraud_ring_proximity` — Graph distance to known fraud cases
- `shared_device_count` — Identities sharing same device fingerprint
- `shared_phone_count` — Identities sharing same phone number
- `network_risk_score` — Aggregated risk from 2-hop neighborhood

**Cross-Source Consistency Features:**
- `cross_source_consistency_score` — Overall data consistency (0-1)
- `nia_gis_consistency` — NIA vs GIS agreement
- `nia_ssnit_consistency` — NIA vs SSNIT agreement
- `phone_name_consistency` — Telecom record vs NIA name

**Watchlist and Sanctions Features:**
- `interpol_flag` — Interpol Red Notice match
- `ofac_sdn_flag` — OFAC SDN list match
- `ghana_police_wanted_flag` — Ghana Police wanted list
- `eoco_flag` — Economic and Organised Crime Office watchlist
- `sanctions_match_count` — Total sanctions list hits

**Institutional History Features:**
- `prior_fraud_reports_count` — Fraud reports filed against identity
- `declined_applications_30d` — Financial application declines in 30 days
- `account_closure_count_1y` — Accounts closed in last year
- `adverse_insurance_claims` — Insurance fraud flags

### 2.3 Model Training

```python
# Training data requirements
TRAINING_DATA = {
    "size": "500,000+ labeled identity query events",
    "labels": {
        "fraud": "confirmed fraud cases from institutional partners",
        "legitimate": "verified clean transactions"
    },
    "class_balance": "1:20 fraud:legitimate (oversampled with SMOTE)",
    "time_split": "train on T-180d to T-30d, validate on T-30d to T-7d, test on T-7d to T",
    "feature_engineering": "rolling windows: 1h, 24h, 7d, 30d, 90d"
}

# Model hyperparameters (XGBoost)
XGB_PARAMS = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "scale_pos_weight": 20,  # class imbalance
    "eval_metric": ["auc", "aucpr"],
    "early_stopping_rounds": 50
}
```

### 2.4 Model Performance Targets

| Metric | Target | Current |
|---|---|---|
| AUROC | > 0.95 | TBD (pre-production) |
| Precision at 5% FPR | > 0.80 | TBD |
| Recall at 10% FPR | > 0.75 | TBD |
| Inference latency (p99) | < 50ms | TBD |
| SHAP explanation time | < 100ms | TBD |

### 2.5 Model Governance

- **Model versioning:** Every trained model is versioned and stored in S3 with full metadata
- **A/B testing:** New model versions run in shadow mode for 2 weeks before promotion
- **Drift detection:** Feature distribution monitored weekly; alert if KS-test p-value < 0.05
- **Retraining trigger:** Drift detected, or AUROC drops > 2% on recent data
- **Human review:** All CRITICAL-band scores (750+) reviewed by fraud analyst before action
- **Model explainability:** SHAP values returned for every score; regulators can request full explanation
- **Bias monitoring:** Score distributions monitored across region, gender, age groups

---

## 3. Entity Resolution (Deduplication)

Multiple data sources may contain records for the same person. The entity resolution engine:

```
Input: Multiple records from NIA, GIS, SSNIT, DVLA, etc.

Step 1: Blocking
  - Block on: (DOB_year, first_3_chars_surname)
  - Reduces candidate pairs from O(n²) to O(n log n)

Step 2: Candidate Pair Scoring
  - Name similarity: Jaro-Winkler distance (threshold: 0.92)
  - DOB match: Exact required (with tolerance for known transcription errors)
  - Address similarity: Fuzzy match (Levenshtein distance)
  - Phone overlap: Exact match bonus
  - Composite score: Weighted sum of field similarities

Step 3: Merge Decision
  - Score > 0.90: Auto-merge
  - Score 0.75-0.90: Flag for human review
  - Score < 0.75: Keep as separate records

Step 4: Golden Record Creation
  - Primary source: NIA (highest authoritative weight)
  - Conflict resolution: Most recent + highest confidence wins
  - Confidence score: Per-field confidence based on source agreement
```

---

## 4. Behavioral Anomaly Detection

Beyond the fraud score, behavioral anomalies are detected using:

**Isolation Forest Model:**
- Trained on 180 days of baseline legitimate query behavior
- Detects deviations in: query timing, location patterns, field access patterns
- Returns anomaly score (0-1) and anomaly type
- Threshold: Score > 0.7 triggers review flag

**Rule-Based Anomaly Engine (complementing ML):**
```python
ANOMALY_RULES = [
    "Query from new IP after 6+ months of same IP",
    "First query from international IP for Ghana-based institution",
    "Query for own institution's employee record (potential insider threat)",
    "Bulk identity lookup > 50 records in 1 hour",
    "Query for recently deceased individual",
    "Repeated queries for same identity across multiple accounts",
    "Lookup immediately followed by another institution lookup (coordinated fraud signal)",
]
```

---

## 5. Continuous Learning

The platform improves over time through:

1. **Confirmed Fraud Feedback Loop** — When institutions confirm fraud, those cases are labeled and used in next training cycle
2. **False Positive Feedback** — Institutions can flag false positives; reduces model bias
3. **New Feature Ingestion** — New data sources automatically feature-engineered into model
4. **Quarterly Model Refresh** — Full retraining on rolling 12-month window

---

*AI/ML questions: ml-team@idintel.com.gh*
