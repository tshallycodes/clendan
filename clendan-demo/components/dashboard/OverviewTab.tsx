"use client";

import { ArrowRight } from "lucide-react";
import { StatCard } from "@/components/ui/StatCard";
import { ExecutionChart } from "@/components/dashboard/ExecutionChart";
import { MOCK_EXECUTIONS } from "@/lib/mock-data";
import { formatCurrency } from "@/lib/utils";
import { cn } from "@/lib/utils";

const STATUS_STYLES = {
  auto: { label: "✓ Auto", class: "text-brand-green" },
  pending: { label: "⏳ Pending", class: "text-brand-info" },
  flagged: { label: "⚠ Flagged", class: "text-brand-danger" },
  rejected: { label: "✗ Rejected", class: "text-brand-danger" },
} as const;

export function OverviewTab() {
  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard value={14} label="Invoices Processed Today" change="+3 from yesterday" changeDirection="up" />
        <StatCard value={47} label="Hours Saved This Month" suffix=".5 hrs" change="On track" changeDirection="up" />
        <StatCard value={3} label="Pending Approvals" change="2 urgent" changeDirection="neutral" />
        <StatCard value={1} label="Fraud Flags" change="Review required" changeDirection="down" />
      </div>

      {/* Chart */}
      <ExecutionChart />

      {/* Recent executions */}
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-brand-border">
          <h3 className="font-heading font-semibold text-brand-text text-sm">Recent Executions</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-brand-border">
                {["Time", "Worker", "Action", "Amount", "Status", ""].map((h) => (
                  <th key={h} className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-5 py-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MOCK_EXECUTIONS.map((exec) => {
                const status = STATUS_STYLES[exec.status];
                return (
                  <tr key={exec.id} className="border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors">
                    <td className="px-5 py-3 text-xs font-mono text-brand-muted">{exec.time}</td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-text">{exec.worker.replace(" Worker", "")}</td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-text">{exec.action}</td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-text">
                      {exec.amount ? formatCurrency(exec.amount, exec.currency) : "—"}
                    </td>
                    <td className={cn("px-5 py-3 text-xs font-mono", status.class)}>{status.label}</td>
                    <td className="px-5 py-3">
                      <button className="text-brand-muted hover:text-brand-text transition-colors">
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Active workers */}
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-brand-border">
          <h3 className="font-heading font-semibold text-brand-text text-sm">Active Workers</h3>
        </div>
        <div className="divide-y divide-brand-border">
          {[
            { name: "Invoice Processing Worker", note: "14 invoices processed today" },
            { name: "AI Accountant Worker", note: "Last action 2 mins ago" },
          ].map((w) => (
            <div key={w.name} className="px-5 py-4 flex items-center gap-4">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-green opacity-60" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand-green" />
              </span>
              <div className="flex-1">
                <div className="text-xs font-mono text-brand-text">{w.name}</div>
                <div className="text-xs font-mono text-brand-muted">{w.note}</div>
              </div>
              <span className="text-[10px] font-mono bg-[rgba(0,200,83,0.08)] text-brand-green border border-[rgba(0,200,83,0.2)] px-2 py-0.5 rounded-sm">
                RUNNING
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
