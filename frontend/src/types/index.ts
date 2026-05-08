// Core platform types

export type VerificationStatus = "VERIFIED" | "PARTIAL_MATCH" | "NOT_FOUND" | "BLOCKED";
export type RiskBand = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ReportType =
  | "QUICK_SUMMARY"
  | "FULL_INTELLIGENCE_DOSSIER"
  | "FRAUD_INVESTIGATION_REPORT"
  | "COMPLIANCE_CERTIFICATE"
  | "BEHAVIORAL_ANOMALY_REPORT";

export interface IdentityProfile {
  identity_id: string;
  ghana_card_number?: string;
  full_name: string;
  date_of_birth?: string;
  gender?: string;
  nationality: string;
  address?: {
    region?: string;
    district?: string;
    town?: string;
  };
  document_status?: {
    ghana_card: string;
    expiry_date?: string;
    issue_date?: string;
  };
  phone_verified: boolean;
  photo_available: boolean;
  data_sources: string[];
  last_verified?: string;
}

export interface VerifyResponse {
  request_id: string;
  timestamp: string;
  verification_status: VerificationStatus;
  confidence_score: number;
  identity_profile?: IdentityProfile;
  audit_reference: string;
}

export interface FraudScoreResponse {
  request_id: string;
  identity_id: string;
  fraud_score: {
    overall_score: number;
    score_band: RiskBand;
    score_interpretation: string;
    contributing_factors: Array<{
      factor: string;
      weight: number;
      value: string;
      explanation: string;
    }>;
    watchlist_status: "CLEAR" | "FLAGGED" | "CONFIRMED";
    sanctions_status: "CLEAR" | "MATCH" | "POSSIBLE_MATCH";
    model_version: string;
    score_timestamp: string;
  };
  recommended_action: "PROCEED" | "REVIEW" | "DECLINE" | "ESCALATE";
  audit_reference: string;
}

export interface IntelligenceReport {
  request_id: string;
  report_id: string;
  identity_id: string;
  report_type: ReportType;
  generated_at: string;
  report: Record<string, { summary: string; confidence?: string }>;
  report_pdf_url?: string;
  report_expires_at?: string;
  audit_reference: string;
  ai_model_used: string;
  disclaimer: string;
}

export interface AuditEvent {
  event_id: string;
  timestamp: string;
  institution_id: string;
  user_id: string;
  user_role: string;
  request_id: string;
  endpoint: string;
  query_type: string;
  purpose_code: string;
  subject_id_hash?: string;
  response_status: string;
  http_status_code: number;
  response_time_ms?: number;
}

export interface Institution {
  institution_id: string;
  name: string;
  institution_type: string;
  status: string;
  subscription_tier: string;
  onboarded_at?: string;
}

export interface CurrentUser {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  institution_id: string;
  institution_name: string;
  institution_type: string;
}
