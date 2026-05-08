"""Prompt templates for Claude AI intelligence reports.

These prompts are designed to:
1. Never request or reproduce raw PII — all subjects are tokenized
2. Produce structured, professional-grade reports
3. Clearly label confidence levels: [CONFIRMED], [PROBABLE], [POSSIBLE]
4. Support both quick summaries and full investigation dossiers
"""

SYSTEM_PROMPT = """
You are an expert identity intelligence analyst for IDIntel Ghana, a government-grade identity verification and intelligence platform operating under the Ghana Data Protection Act 2012 and the NIA Act 2006. You serve authorized institutions including banks, law enforcement, telecoms, insurance companies, and government agencies.

Your role is to analyze anonymized identity data and generate professional intelligence reports.

CRITICAL RULES:
1. Do NOT speculate beyond the provided data
2. Do NOT generate or infer personal information not in the data
3. Do NOT reference any real individuals or make assumptions about ethnicity, religion, or politics
4. Label every factual claim as [CONFIRMED], [PROBABLE], or [POSSIBLE]
5. All persons in the data are represented by tokens (e.g., [PERSON_A]) — use these tokens throughout
6. Use professional, neutral intelligence analyst language
7. Always include an analyst confidence assessment at the end
8. If data is insufficient for a section, state "INSUFFICIENT DATA" rather than speculating
""".strip()

QUICK_SUMMARY_PROMPT = """
Generate a concise identity intelligence summary for the following anonymized profile. This is for institutional use by a {institution_type}.

ANONYMIZED IDENTITY DATA:
{anonymized_data}

Generate the following sections: {sections}

FORMAT REQUIREMENTS:
- Each section: 2-4 sentences maximum
- Start each section with the section name in ALL CAPS
- Label facts as [CONFIRMED], [PROBABLE], or [POSSIBLE]
- Conclude with a one-sentence ANALYST_RECOMMENDATION: PROCEED / REVIEW / DECLINE / ESCALATE

IDENTITY_OVERVIEW: Describe verification status, document validity, and data source confidence.
RISK_ASSESSMENT: Interpret the fraud score, watchlist status, and key risk factors.
INSTITUTIONAL_HISTORY: Describe recent institutional query patterns and what they indicate.
BEHAVIORAL_NOTES: Note any anomalous patterns or absence of anomalies.
ANALYST_RECOMMENDATION: One-sentence recommendation with confidence level.
""".strip()

INVESTIGATION_REPORT_PROMPT = """
Generate a formal intelligence dossier for an authorized investigation.

INVESTIGATION REFERENCE: {investigation_reference}
LEGAL AUTHORITY: {legal_authority}
ANALYSIS WINDOW: {time_window_days} days

SUBJECT PROFILE (ANONYMIZED):
{anonymized_data}

NETWORK CONTEXT:
{network_summary}

Generate a formal investigation report with the following sections. Use professional law enforcement intelligence report style.

1. SUBJECT_OVERVIEW
Summarize the subject's verified identity status, document validity, and data reliability. Label each finding as [CONFIRMED], [PROBABLE], or [POSSIBLE].

2. TIMELINE_RECONSTRUCTION
Reconstruct the chronological sequence of events based on available data within the analysis window. Note gaps.

3. NETWORK_ANALYSIS
Analyze the subject's known network. Identify high-risk associates, shared identifiers, and network risk indicators. Clearly distinguish between confirmed connections and inferred relationships.

4. BEHAVIORAL_ANALYSIS
Analyze behavioral patterns: query velocity, timing, geographic consistency, institutional interaction patterns. Note anomalies or their absence.

5. RISK_ASSESSMENT
Synthesize the fraud score, watchlist status, network risk, and behavioral signals into an overall risk assessment. Quantify confidence.

6. INTELLIGENCE_GAPS
List what additional information would strengthen the intelligence picture. Recommend follow-up investigative steps.

CONFIDENCE SCALE: [CONFIRMED] = direct data, [PROBABLE] = strong inference, [POSSIBLE] = weak inference

End with: ANALYST_CONFIDENCE: HIGH / MEDIUM / LOW — and one sentence justification.
""".strip()

COMPLIANCE_CERT_PROMPT = """
Generate a compliance verification certificate for the following anonymized identity.

This certificate is for regulatory compliance purposes under {regulatory_framework}.

ANONYMIZED IDENTITY DATA:
{anonymized_data}

Generate a formal compliance certificate including:

1. VERIFICATION_STATUS: Overall verification result and confidence score
2. DOCUMENT_VALIDITY: Document status and expiry information
3. WATCHLIST_CLEARANCE: Confirmation of watchlist and sanctions screening
4. DATA_SOURCES: List of authoritative sources consulted
5. COMPLIANCE_DECLARATION: Formal declaration suitable for regulatory submission
6. CERTIFICATE_LIMITATIONS: Any caveats or limitations of this verification

Use formal, legally appropriate language suitable for regulatory submissions.
""".strip()

BEHAVIORAL_ANOMALY_PROMPT = """
Perform a behavioral anomaly analysis on the following identity profile.

ANONYMIZED IDENTITY DATA:
{anonymized_data}

BEHAVIORAL METRICS:
{behavioral_metrics}

Analyze for the following anomaly types:
1. VELOCITY_ANOMALIES: Unusual query frequency patterns
2. TEMPORAL_ANOMALIES: Unusual timing patterns (off-hours, sudden activity)
3. GEOGRAPHIC_ANOMALIES: Geographic inconsistencies
4. CROSS_INSTITUTION_ANOMALIES: Unusual multi-institution activity patterns
5. BEHAVIORAL_BASELINE_DEVIATION: Deviation from established behavioral profile

For each anomaly type:
- State if anomaly is DETECTED or NOT_DETECTED
- If detected: severity (LOW/MEDIUM/HIGH), description, and recommended action
- If not detected: brief confirmation of normal behavior

Conclude with OVERALL_ANOMALY_ASSESSMENT and RECOMMENDED_ACTION.
""".strip()
