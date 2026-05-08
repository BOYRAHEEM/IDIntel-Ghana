# Compliance Framework — IDIntel Ghana

## Legal and Regulatory Basis

IDIntel Ghana operates under explicit legal authorization and is designed to maintain full compliance with all applicable Ghanaian law, regional standards, and international best practices.

---

## 1. Applicable Laws and Regulations

### 1.1 Primary Ghanaian Legislation

| Act | Relevance | Compliance Requirement |
|---|---|---|
| **Data Protection Act 2012 (Act 843)** | Governs processing of personal data of Ghanaian citizens | Full compliance — processing principles, data subject rights, notification requirements |
| **National Identification Authority Act 2006 (Act 707)** | Governs access to NIA data and Ghana Card system | Formal authorization agreement with NIA required per institution |
| **Electronic Transactions Act 2008 (Act 772)** | Governs digital records, electronic signatures | All digital audit records are legally valid electronic documents |
| **Computer Crimes Act 2008 (Act 722)** | Criminalizes unauthorized access | Platform must not facilitate unauthorized access; all access is authorized and logged |
| **Anti-Money Laundering Act 2020 (Act 1044)** | AML/CFT requirements for financial institutions | Fraud scores and identity verification support AML compliance |
| **Bank of Ghana Cybersecurity Directive 2018** | Security requirements for financial sector | Controls implemented for all bank/fintech clients |
| **Insurance Act 2021 (Act 1061)** | Insurance sector data requirements | Compliant data handling for insurance institution clients |
| **Electronic Communications Act 2008 (Act 775)** | Telecom data handling | Compliant data sharing with NCA-licensed operators |

### 1.2 Regional and International Standards

| Standard | Relevance |
|---|---|
| **ECOWAS Supplementary Act on Data Protection (2010)** | Regional data protection framework for cross-border sharing |
| **African Union Convention on Cybersecurity and Data Protection (2014)** | AU-level data protection principles |
| **ISO/IEC 27001:2022** | Information security management system alignment |
| **ISO/IEC 27018:2019** | PII protection in cloud environments |
| **SOC 2 Type II** | Security, availability, processing integrity, confidentiality, privacy |
| **PCI-DSS v4.0** | For any payment-adjacent financial institution integrations |
| **FATF Recommendations** | AML/CFT due diligence support |

---

## 2. Ghana Data Protection Act 2012 (Act 843) Compliance

### 2.1 Data Processing Principles

| Principle | Implementation |
|---|---|
| **Lawful Basis** | Processing only with explicit institutional authorization from NIA and Data Protection Commission (DPC) registration |
| **Purpose Limitation** | Each API request requires a `purpose_code` field; responses only contain data relevant to stated purpose |
| **Data Minimization** | Per-institution data scope contracts enforce minimum necessary data return |
| **Accuracy** | Multi-source verification with confidence scores; correction mechanism for inaccurate records |
| **Storage Limitation** | Query results cached maximum 5 minutes; no permanent storage of query results without purpose |
| **Security** | AES-256-GCM encryption, access controls, audit logs (see SECURITY.md) |
| **Accountability** | Full audit trail of all data access; DPC reportable under breach provisions |

### 2.2 Data Subject Rights

Individuals (data subjects) retain rights under Act 843. IDIntel Ghana supports these rights:

| Right | Mechanism |
|---|---|
| **Right of Access** | Citizens can submit access requests to IDIntel Ghana; we provide a log of which institutions queried their record |
| **Right to Correction** | Inaccuracy reports forwarded to NIA and relevant source institutions |
| **Right to Object** | Citizens can flag unauthorized institutional queries |
| **Breach Notification** | DPC notified within 72 hours of confirmed breach; affected institutions notified immediately |

### 2.3 Data Controller vs Processor

| Role | Entity | Responsibilities |
|---|---|---|
| **Data Controller** | NIA (for Ghana Card data) | Determines purpose and means of processing |
| **Data Controller** | Individual Institutions (for their own queries) | Responsible for ensuring lawful basis for each query |
| **Data Processor** | IDIntel Ghana Ltd | Processes data on behalf of controllers; implements technical controls |
| **Sub-processor** | AWS (cloud infrastructure) | DPA executed with AWS; GDPR-aligned EU Standard Contractual Clauses |

---

## 3. NIA Integration Authorization Framework

### 3.1 Required Agreements

Before going live, IDIntel Ghana must execute:

1. **NIA Data Sharing Agreement** — Authorizing system-to-system access to Ghana Card data
2. **DPC Registration** — Register as a data processor with the Data Protection Commission
3. **Per-Institution Authorization Letters** — Each institution must obtain NIA authorization for their use case

### 3.2 Permitted Query Types by NIA Authorization Level

| Authorization Level | Permitted Queries |
|---|---|
| Level 1 (Basic) | Name, DOB, Ghana Card number validation |
| Level 2 (Standard) | + Address, photo reference, document validity |
| Level 3 (Enhanced) | + Biometric hash comparison, full record |
| Level 4 (Law Enforcement) | + Investigation-grade full record, relationship flags |

---

## 4. Purpose Codes and Legal Basis

Every API query must include a `purpose_code`. Valid purpose codes:

```
ACCOUNT_OPENING       — Bank/fintech account opening (legal basis: legal obligation)
KYC_REFRESH           — Periodic KYC update (legal basis: legal obligation)
LOAN_APPLICATION      — Credit assessment (legal basis: legitimate interest)
INSURANCE_UNDERWRITING — Policy risk assessment (legal basis: contract)
SIM_REGISTRATION      — Telecom SIM registration compliance (legal basis: legal obligation)
AML_SCREENING         — Anti-money laundering check (legal basis: legal obligation)
FRAUD_INVESTIGATION   — Active fraud investigation (legal basis: legal obligation)
CLAIMS_VERIFICATION   — Insurance claim verification (legal basis: contract)
LAW_ENFORCEMENT_QUERY — Criminal investigation (legal basis: legal obligation + court order)
IMMIGRATION_CONTROL   — Border control processing (legal basis: legal obligation)
BENEFIT_VERIFICATION  — Government benefit eligibility (legal basis: legal obligation)
REGULATORY_COMPLIANCE — Regulatory reporting obligation (legal basis: legal obligation)
CREDIT_SCORING        — Credit bureau scoring (legal basis: legitimate interest)
```

---

## 5. Audit Requirements

### 5.1 Retention Schedule

| Data Type | Retention Period | Storage | Deletion Method |
|---|---|---|---|
| Audit logs (all query events) | 7 years | S3 Glacier + PostgreSQL WORM | Secure deletion after retention |
| Identity query results (cached) | 5 minutes | Redis (in-memory) | Automatic TTL expiry |
| Generated intelligence reports | 90 days | S3 encrypted | Automatic + manual delete |
| API access logs | 2 years | ELK Stack + S3 | Log rotation |
| Security incident records | 10 years | S3 Glacier | Legal hold |
| User access records | 5 years | PostgreSQL | Secure deletion |

### 5.2 Audit Export for Institutions

Each institution can export their complete audit trail:
- Format: JSON, CSV, or PDF
- Content: All queries made by their users, timestamps, results, user IDs
- Frequency: On-demand or scheduled monthly
- Purpose: Internal compliance, regulatory submissions, legal proceedings

---

## 6. Cross-Border Data Transfer Controls

Ghana Card data is classified as **national sensitive data**. Cross-border transfer is:

- **Prohibited** without explicit NIA and DPC approval
- IDIntel Ghana's AWS infrastructure is in the **af-south-1 (Cape Town)** region by default
- Cross-border transfer to EU/US for AI processing (Claude API) uses **data anonymization**:
  - All PII replaced with tokens before sending to external AI APIs
  - Only anonymized, non-personally-identifiable context leaves Ghana
  - Re-identification tokens are stored locally and never transmitted

---

## 7. Institutional Onboarding Compliance Checklist

Before an institution is granted API access:

```
□ Signed Master Service Agreement (MSA)
□ Data Processing Agreement (DPA) executed
□ Institution's own NIA authorization letter provided
□ Legal basis assessment completed for their use cases
□ Security assessment of institution's integration completed
□ Designated Data Protection Officer (DPO) contact registered
□ Emergency/breach notification contacts registered
□ IP allowlist submitted and configured
□ mTLS certificate issued and tested
□ Purpose codes approved and configured in system
□ Data scope contract agreed and implemented
□ Staff training on platform use completed
□ SLA agreement signed
□ Audit export access tested
```

---

## 8. Breach Response and Regulatory Notification

### Timeline

| Time | Action |
|---|---|
| T+0 | Breach detected |
| T+1 hour | Internal escalation to CISO and legal |
| T+4 hours | Scope assessment completed |
| T+24 hours | Affected institutions notified |
| T+72 hours | DPC notified (Act 843 requirement) |
| T+7 days | Full incident report submitted to DPC |
| T+30 days | Remediation report submitted |

### Notification Content (Act 843 Requirements)

Breach notifications must include:
- Nature of the breach
- Categories and approximate number of data subjects affected
- Categories and approximate number of records affected
- Likely consequences of the breach
- Measures taken or proposed to address the breach

---

*Compliance queries: compliance@idintel.com.gh | Legal: legal@idintel.com.gh*
