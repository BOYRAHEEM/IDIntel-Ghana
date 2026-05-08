import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Search, Shield, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { apiClient } from "../services/api";
import type { VerifyResponse, FraudScoreResponse } from "../types";

const verifySchema = z.object({
  query_type: z.enum(["ghana_card", "name_dob", "phone_number", "passport"]),
  ghana_card_number: z.string().optional(),
  full_name: z.string().optional(),
  date_of_birth: z.string().optional(),
  phone_number: z.string().optional(),
  passport_number: z.string().optional(),
  purpose_code: z.string().min(4),
});

type VerifyFormData = z.infer<typeof verifySchema>;

const PURPOSE_CODES = [
  { value: "ACCOUNT_OPENING", label: "Account Opening" },
  { value: "KYC_REFRESH", label: "KYC Refresh" },
  { value: "LOAN_APPLICATION", label: "Loan Application" },
  { value: "AML_SCREENING", label: "AML Screening" },
  { value: "FRAUD_INVESTIGATION", label: "Fraud Investigation" },
  { value: "SIM_REGISTRATION", label: "SIM Registration" },
  { value: "INSURANCE_UNDERWRITING", label: "Insurance Underwriting" },
  { value: "REGULATORY_COMPLIANCE", label: "Regulatory Compliance" },
];

export default function VerifyIdentity() {
  const [verifyResult, setVerifyResult] = useState<VerifyResponse | null>(null);
  const [fraudResult, setFraudResult] = useState<FraudScoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, watch, formState: { errors } } = useForm<VerifyFormData>({
    resolver: zodResolver(verifySchema),
    defaultValues: { query_type: "ghana_card" },
  });

  const queryType = watch("query_type");

  const onSubmit = async (data: VerifyFormData) => {
    setLoading(true);
    setError(null);
    setVerifyResult(null);
    setFraudResult(null);

    try {
      const result = await apiClient.verifyIdentity(data);
      setVerifyResult(result);

      if (result.identity_profile?.identity_id) {
        const fraud = await apiClient.getFraudScore({
          identity_id: result.identity_profile.identity_id,
          purpose_code: data.purpose_code,
        });
        setFraudResult(fraud);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <Shield className="w-8 h-8 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Identity Verification</h1>
          <p className="text-sm text-gray-500">Query authorized identity sources</p>
        </div>
      </div>

      {/* Search Form */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Query Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Method
              </label>
              <select
                {...register("query_type")}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="ghana_card">Ghana Card Number</option>
                <option value="name_dob">Name + Date of Birth</option>
                <option value="phone_number">Phone Number</option>
                <option value="passport">Passport Number</option>
              </select>
            </div>

            {/* Purpose Code */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Purpose <span className="text-red-500">*</span>
              </label>
              <select
                {...register("purpose_code")}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {PURPOSE_CODES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Conditional fields */}
          {queryType === "ghana_card" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ghana Card Number
              </label>
              <input
                {...register("ghana_card_number")}
                placeholder="GHA-123456789-0"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {errors.ghana_card_number && (
                <p className="text-xs text-red-500 mt-1">{errors.ghana_card_number.message}</p>
              )}
            </div>
          )}

          {queryType === "name_dob" && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  {...register("full_name")}
                  placeholder="Kwame Asante Mensah"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
                <input
                  type="date"
                  {...register("date_of_birth")}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          )}

          {queryType === "phone_number" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
              <input
                {...register("phone_number")}
                placeholder="+233 24 000 0000"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {queryType === "passport" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Passport Number</label>
              <input
                {...register("passport_number")}
                placeholder="G1234567"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-red-50 border border-red-200">
              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Search className="w-4 h-4" />
            {loading ? "Verifying..." : "Verify Identity"}
          </button>
        </form>
      </div>

      {/* Results */}
      {verifyResult && (
        <div className="space-y-4">
          {/* Verification Status Card */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Verification Result</h2>
              <StatusBadge status={verifyResult.verification_status} />
            </div>

            {verifyResult.identity_profile && (
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-3">
                  <ProfileField label="Full Name" value={verifyResult.identity_profile.full_name} />
                  <ProfileField label="Nationality" value={verifyResult.identity_profile.nationality} />
                  <ProfileField label="Gender" value={verifyResult.identity_profile.gender} />
                  {verifyResult.identity_profile.address && (
                    <ProfileField label="Region" value={verifyResult.identity_profile.address.region} />
                  )}
                </div>
                <div className="space-y-3">
                  {verifyResult.identity_profile.ghana_card_number && (
                    <ProfileField
                      label="Ghana Card"
                      value={verifyResult.identity_profile.ghana_card_number}
                      mono
                    />
                  )}
                  {verifyResult.identity_profile.document_status && (
                    <ProfileField
                      label="Card Status"
                      value={verifyResult.identity_profile.document_status.ghana_card}
                    />
                  )}
                  <ProfileField
                    label="Data Sources"
                    value={verifyResult.identity_profile.data_sources.join(", ")}
                  />
                  <ProfileField
                    label="Confidence"
                    value={`${(verifyResult.confidence_score * 100).toFixed(1)}%`}
                  />
                </div>
              </div>
            )}

            <div className="mt-4 pt-4 border-t border-gray-100">
              <p className="text-xs text-gray-400">
                Request ID: {verifyResult.request_id} · Audit Ref: {verifyResult.audit_reference}
              </p>
            </div>
          </div>

          {/* Fraud Score Card */}
          {fraudResult && (
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Fraud Risk Assessment</h2>
              <div className="flex items-center gap-6 mb-4">
                <div className="text-center">
                  <div className={`text-4xl font-bold ${scoreColor(fraudResult.fraud_score.overall_score)}`}>
                    {fraudResult.fraud_score.overall_score}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">out of 1000</div>
                </div>
                <div>
                  <RiskBadge band={fraudResult.fraud_score.score_band} />
                  <p className="text-sm text-gray-600 mt-2 max-w-md">
                    {fraudResult.fraud_score.score_interpretation}
                  </p>
                  <p className="text-sm font-medium text-gray-700 mt-2">
                    Recommended: <span className={actionColor(fraudResult.recommended_action)}>
                      {fraudResult.recommended_action}
                    </span>
                  </p>
                </div>
              </div>

              {fraudResult.fraud_score.contributing_factors.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Contributing Factors</h3>
                  <div className="space-y-2">
                    {fraudResult.fraud_score.contributing_factors.map((f, i) => (
                      <div key={i} className="text-sm bg-gray-50 rounded px-3 py-2">
                        <span className="font-medium text-gray-700">{f.factor}: </span>
                        <span className="text-gray-600">{f.explanation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    VERIFIED: { bg: "bg-green-100 text-green-800", icon: CheckCircle },
    PARTIAL_MATCH: { bg: "bg-yellow-100 text-yellow-800", icon: AlertTriangle },
    NOT_FOUND: { bg: "bg-gray-100 text-gray-700", icon: XCircle },
    BLOCKED: { bg: "bg-red-100 text-red-800", icon: XCircle },
  }[status] || { bg: "bg-gray-100 text-gray-700", icon: Shield };

  const Icon = config.icon;
  return (
    <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${config.bg}`}>
      <Icon className="w-4 h-4" />
      {status.replace("_", " ")}
    </span>
  );
}

function RiskBadge({ band }: { band: string }) {
  const colors = {
    LOW: "bg-green-100 text-green-800",
    MEDIUM: "bg-yellow-100 text-yellow-800",
    HIGH: "bg-orange-100 text-orange-800",
    CRITICAL: "bg-red-100 text-red-800",
  }[band] || "bg-gray-100 text-gray-700";

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${colors}`}>
      {band} RISK
    </span>
  );
}

function ProfileField({ label, value, mono = false }: { label: string; value?: string; mono?: boolean }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</dt>
      <dd className={`text-sm text-gray-900 mt-0.5 ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

function scoreColor(score: number): string {
  if (score <= 200) return "text-green-600";
  if (score <= 500) return "text-yellow-600";
  if (score <= 750) return "text-orange-600";
  return "text-red-600";
}

function actionColor(action: string): string {
  const colors: Record<string, string> = {
    PROCEED: "text-green-700",
    REVIEW: "text-yellow-700",
    DECLINE: "text-orange-700",
    ESCALATE: "text-red-700",
  };
  return colors[action] || "text-gray-700";
}
