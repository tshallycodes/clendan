"use client";

import { useState } from "react";
import { Bell, Search } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { OverviewTab } from "@/components/dashboard/OverviewTab";
import { ApprovalsTab } from "@/components/dashboard/ApprovalsTab";
import { AuditTrailTab } from "@/components/dashboard/AuditTrailTab";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("overview");

  const renderTab = () => {
    switch (activeTab) {
      case "overview": return <OverviewTab />;
      case "approvals": return <ApprovalsTab />;
      case "audit": return <AuditTrailTab />;
      default:
        return (
          <div className="bg-brand-surface border border-brand-border rounded-sm px-6 py-12 text-center text-brand-muted font-mono text-sm">
            This section is not available in the demo.
          </div>
        );
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-brand-bg">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Demo mode banner */}
        <div className="bg-[rgba(245,166,35,0.08)] border-b border-[rgba(245,166,35,0.2)] px-5 py-2 text-center">
          <span className="text-brand-warning text-xs font-mono tracking-wider">
            ⚠ DEMO MODE — All data is mock. No real financial operations are performed.
          </span>
        </div>

        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-brand-border bg-brand-surface shrink-0">
          <div>
            <h1 className="font-heading font-bold text-brand-text text-base capitalize">
              {activeTab === "audit" ? "Audit Trail" : activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
            </h1>
            <p className="text-brand-muted text-xs font-mono">Tenant: Acme Corp · Region: EU</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
              <Search className="w-3.5 h-3.5 text-brand-muted" />
              <input
                type="text"
                placeholder="Search executions..."
                className="bg-transparent text-xs font-mono text-brand-text placeholder:text-brand-muted outline-none w-40"
              />
            </div>
            <button className="relative text-brand-muted hover:text-brand-text transition-colors p-2">
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-brand-danger rounded-full" />
            </button>
            <div className="w-8 h-8 rounded-sm bg-brand-elevated border border-brand-border flex items-center justify-center font-heading font-bold text-brand-green text-xs">
              AC
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {renderTab()}
        </main>
      </div>
    </div>
  );
}
