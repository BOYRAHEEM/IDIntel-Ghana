import React from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Shield,
  Search,
  AlertTriangle,
  FileText,
  Activity,
  Settings,
  Key,
  LogOut,
  Menu,
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import VerifyIdentity from "./pages/VerifyIdentity";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30000, retry: 1 },
  },
});

const NAV_LINKS = [
  { to: "/dashboard", label: "Dashboard", icon: Shield },
  { to: "/verify", label: "Verify Identity", icon: Search },
  { to: "/fraud", label: "Fraud Analysis", icon: AlertTriangle },
  { to: "/reports", label: "Intelligence Reports", icon: FileText },
  { to: "/audit", label: "Audit Logs", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/api-keys", label: "API Keys", icon: Key },
];

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-5 border-b border-gray-200">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-gray-900">IDIntel Ghana</div>
            <div className="text-xs text-gray-500">Secure Platform</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User info */}
        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">Institution User</p>
              <p className="text-xs text-gray-500">Analyst</p>
            </div>
            <button
              onClick={() => {
                localStorage.clear();
                window.location.href = "/login";
              }}
              className="p-1.5 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100"
              title="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="h-16 bg-white border-b border-gray-200 flex items-center px-6 justify-between">
          <button className="p-2 text-gray-400 hover:text-gray-600 rounded lg:hidden">
            <Menu className="w-5 h-5" />
          </button>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs text-gray-500">
              All queries are logged under Act 843
            </span>
            <div className="flex items-center gap-1.5 text-xs text-green-600">
              <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
              Secure Session
            </div>
          </div>
        </div>
        {children}
      </main>
    </div>
  );
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="p-6 flex items-center justify-center min-h-96">
      <div className="text-center text-gray-400">
        <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p className="text-lg font-medium">{title}</p>
        <p className="text-sm mt-1">Coming soon</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/verify" element={<VerifyIdentity />} />
            <Route path="/fraud" element={<PlaceholderPage title="Fraud Analysis" />} />
            <Route path="/reports" element={<PlaceholderPage title="Intelligence Reports" />} />
            <Route path="/reports/new" element={<PlaceholderPage title="Generate Report" />} />
            <Route path="/audit" element={<PlaceholderPage title="Audit Logs" />} />
            <Route path="/settings" element={<PlaceholderPage title="Settings" />} />
            <Route path="/api-keys" element={<PlaceholderPage title="API Key Management" />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
