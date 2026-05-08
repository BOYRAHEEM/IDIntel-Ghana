import React from "react";
import { Shield, Search, FileText, AlertTriangle, TrendingUp, Activity } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../services/api";

const stats = [
  {
    label: "Verifications Today",
    value: "—",
    icon: Shield,
    color: "text-blue-600",
    bg: "bg-blue-50",
    description: "Identity lookups",
  },
  {
    label: "Fraud Scores",
    value: "—",
    icon: AlertTriangle,
    color: "text-orange-600",
    bg: "bg-orange-50",
    description: "Risk assessments",
  },
  {
    label: "AI Reports",
    value: "—",
    icon: FileText,
    color: "text-purple-600",
    bg: "bg-purple-50",
    description: "Intelligence generated",
  },
  {
    label: "API Calls (30d)",
    value: "—",
    icon: Activity,
    color: "text-green-600",
    bg: "bg-green-50",
    description: "Total platform queries",
  },
];

const recentActivity = [
  { type: "VERIFIED", label: "Identity verified", time: "2 min ago", band: "LOW" },
  { type: "PARTIAL_MATCH", label: "Partial match — review needed", time: "8 min ago", band: "MEDIUM" },
  { type: "FRAUD_SCORE", label: "HIGH risk score generated", time: "15 min ago", band: "HIGH" },
  { type: "REPORT", label: "Intelligence report generated", time: "23 min ago", band: null },
  { type: "VERIFIED", label: "Identity verified", time: "31 min ago", band: "LOW" },
];

export default function Dashboard() {
  const { data: auditData } = useQuery({
    queryKey: ["audit-logs", "today"],
    queryFn: () => {
      const today = new Date().toISOString().split("T")[0];
      return apiClient.getAuditLogs({ start_date: today, end_date: today, per_page: 5 });
    },
    staleTime: 60000,
  });

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            IDIntel Ghana — Secure Identity Intelligence Platform
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 px-3 py-1.5 rounded-full border border-green-200">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          Platform Operational
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
              <div className="flex items-center justify-between mb-3">
                <span className={`p-2 rounded-lg ${stat.bg}`}>
                  <Icon className={`w-5 h-5 ${stat.color}`} />
                </span>
              </div>
              <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
              <div className="text-sm font-medium text-gray-700 mt-1">{stat.label}</div>
              <div className="text-xs text-gray-400 mt-0.5">{stat.description}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Quick Actions */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
            Quick Actions
          </h2>
          <div className="space-y-2">
            {[
              { label: "Verify Identity", href: "/verify", icon: Shield, color: "text-blue-600" },
              { label: "Search Identities", href: "/search", icon: Search, color: "text-indigo-600" },
              { label: "Generate Report", href: "/reports/new", icon: FileText, color: "text-purple-600" },
              { label: "Fraud Analysis", href: "/fraud", icon: AlertTriangle, color: "text-orange-600" },
              { label: "View Audit Logs", href: "/audit", icon: Activity, color: "text-green-600" },
            ].map((action) => {
              const Icon = action.icon;
              return (
                <a
                  key={action.href}
                  href={action.href}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-gray-50 transition-colors group"
                >
                  <Icon className={`w-4 h-4 ${action.color}`} />
                  <span className="text-sm text-gray-700 group-hover:text-gray-900">
                    {action.label}
                  </span>
                </a>
              );
            })}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="col-span-2 bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
            Recent Activity
          </h2>
          <div className="space-y-3">
            {(auditData?.logs || recentActivity).slice(0, 5).map((item: any, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    item.response_status === "SUCCESS" || item.type === "VERIFIED" ? "bg-green-400" :
                    item.response_status === "ERROR" ? "bg-red-400" : "bg-yellow-400"
                  }`} />
                  <div>
                    <p className="text-sm text-gray-700">
                      {item.query_type || item.label}
                    </p>
                    <p className="text-xs text-gray-400">
                      {item.endpoint || ""} · {item.purpose_code || ""}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  {item.band && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      item.band === "LOW" ? "bg-green-100 text-green-700" :
                      item.band === "MEDIUM" ? "bg-yellow-100 text-yellow-700" :
                      item.band === "HIGH" ? "bg-orange-100 text-orange-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      {item.band}
                    </span>
                  )}
                  <p className="text-xs text-gray-400 mt-1">
                    {item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : item.time}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Platform Notice */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex gap-3">
          <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-blue-800">Authorized Use Only</p>
            <p className="text-sm text-blue-700 mt-0.5">
              All queries are logged and audited under the Ghana Data Protection Act 2012 (Act 843).
              Unauthorized use is a criminal offence. For support: support@idintel.com.gh
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
