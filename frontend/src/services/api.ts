/**
 * IDIntel Ghana API client.
 * Handles authentication, request signing, and error normalization.
 */
import axios, { type AxiosInstance } from "axios";
import type {
  AuditEvent,
  FraudScoreResponse,
  IntelligenceReport,
  VerifyResponse,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "https://api.idintel.com.gh";

class IDIntelAPIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/v1`,
      timeout: 30000,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
    });

    this.client.interceptors.request.use((config) => {
      const token = this.getAccessToken();
      const apiKey = this.getAPIKey();
      const requestId = this.generateRequestId();
      const timestamp = new Date().toISOString();

      if (token) config.headers["Authorization"] = `Bearer ${token}`;
      if (apiKey) config.headers["X-IDIntel-API-Key"] = apiKey;
      config.headers["X-Request-ID"] = requestId;
      config.headers["X-Request-Timestamp"] = timestamp;

      return config;
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          this.clearSession();
          window.location.href = "/login";
        }
        return Promise.reject(this.normalizeError(error));
      }
    );
  }

  // Authentication
  async login(institutionId: string, apiKey: string): Promise<{ access_token: string }> {
    const response = await this.client.post("/auth/token", {
      api_key: apiKey,
      institution_id: institutionId,
    });
    const { access_token } = response.data;
    localStorage.setItem("idintel_token", access_token);
    localStorage.setItem("idintel_api_key", apiKey);
    return response.data;
  }

  logout(): void {
    this.clearSession();
    window.location.href = "/login";
  }

  // Identity Verification
  async verifyIdentity(params: {
    query_type: string;
    ghana_card_number?: string;
    full_name?: string;
    date_of_birth?: string;
    phone_number?: string;
    passport_number?: string;
    purpose_code: string;
  }): Promise<VerifyResponse> {
    const response = await this.client.post("/identity/verify", params);
    return response.data;
  }

  async searchIdentities(params: {
    full_name: string;
    date_of_birth?: string;
    gender?: string;
    region?: string;
    purpose_code: string;
    max_results?: number;
  }) {
    const response = await this.client.post("/identity/search", params);
    return response.data;
  }

  async getIdentityProfile(identityId: string): Promise<VerifyResponse> {
    const response = await this.client.get(`/identity/${identityId}/profile`);
    return response.data;
  }

  async getUsageHistory(identityId: string) {
    const response = await this.client.get(`/identity/${identityId}/usage-history`);
    return response.data;
  }

  // Fraud Detection
  async getFraudScore(params: {
    identity_id: string;
    context?: Record<string, unknown>;
    purpose_code: string;
    include_shap_explanation?: boolean;
  }): Promise<FraudScoreResponse> {
    const response = await this.client.post("/fraud/score", params);
    return response.data;
  }

  async analyzePattern(params: {
    identity_ids: string[];
    analysis_type: string;
    time_window_days: number;
    purpose_code: string;
  }) {
    const response = await this.client.post("/fraud/analyze-pattern", params);
    return response.data;
  }

  // AI Intelligence
  async generateIntelligenceSummary(params: {
    identity_id: string;
    report_type: string;
    include_sections?: string[];
    purpose_code: string;
    format?: "json" | "pdf";
  }): Promise<IntelligenceReport> {
    const response = await this.client.post("/intelligence/summary", params);
    return response.data;
  }

  async generateInvestigationReport(params: {
    subject_identity_id: string;
    investigation_reference: string;
    investigating_officer: string;
    include_network_map?: boolean;
    network_depth?: number;
    time_window_days?: number;
    purpose_code: string;
    legal_authority: string;
    court_order_reference?: string;
  }): Promise<IntelligenceReport> {
    const response = await this.client.post("/intelligence/investigation-report", params);
    return response.data;
  }

  // Audit
  async getAuditLogs(params: {
    start_date?: string;
    end_date?: string;
    user_id?: string;
    query_type?: string;
    page?: number;
    per_page?: number;
  }): Promise<{ total: number; logs: AuditEvent[] }> {
    const response = await this.client.get("/admin/audit/logs", { params });
    return response.data;
  }

  async exportAuditLogs(params: {
    start_date: string;
    end_date: string;
    format: "json" | "csv" | "pdf";
    include_signature_chain?: boolean;
  }) {
    const response = await this.client.post("/admin/audit/export", params);
    return response.data;
  }

  // API Key management
  async createAPIKey(params: {
    name: string;
    scopes: string[];
    is_test?: boolean;
    expires_days?: number;
  }) {
    const response = await this.client.post("/admin/api-keys", params);
    return response.data;
  }

  async revokeAPIKey(keyPrefix: string) {
    const response = await this.client.delete(`/admin/api-keys/${keyPrefix}`);
    return response.data;
  }

  // Helpers
  private getAccessToken(): string | null {
    return localStorage.getItem("idintel_token");
  }

  private getAPIKey(): string | null {
    return localStorage.getItem("idintel_api_key");
  }

  private clearSession(): void {
    localStorage.removeItem("idintel_token");
    localStorage.removeItem("idintel_api_key");
  }

  private generateRequestId(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  private normalizeError(error: unknown): Error {
    if (axios.isAxiosError(error) && error.response?.data) {
      const detail = error.response.data.detail || error.response.data.title || "Request failed";
      return new Error(detail);
    }
    return error as Error;
  }
}

export const apiClient = new IDIntelAPIClient();
