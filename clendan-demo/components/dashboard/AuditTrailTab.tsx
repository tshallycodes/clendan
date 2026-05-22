"use client";

import { useState } from "react";
import { AuditTraceExpand } from "@/components/ui/AuditTraceExpand";
import { MOCK_AUDIT_ENTRIES, type AuditEntry } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

type Filter = "ALL" | AuditEntry["decision"];
const FILTERS: { label: string; value: Filter }[] = [
  { label: "All", value: "ALL" },
  { label: "Auto-Executed", value: "AUTO" },
  { label: "Approved", value: "APPROVE" },
  { label: "Flagged", value: "FLAG" },
  { label: "Rejected", value: "REJECT" },
];

export function AuditTrailTab() {
  const [activeFilter, setActiveFilter] = useState<Filter>("ALL");

  const filtered =
    activeFilter === "ALL"
      ? MOCK_AUDIT_ENTRIES
      : MOCK_AUDIT_ENTRIES.filter((e) => e.decision === activeFilter);

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-brand-border flex flex-col sm:flex-row sm:items-center gap-3">
        <h3 className="font-heading font-semibold text-brand-text text-sm flex-1">Audit Trail</h3>
        <div className="flex gap-1 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setActiveFilter(f.value)}
              className={cn(
                "text-[10px] font-mono px-2.5 py-1 rounded-sm transition-colors",
                activeFilter === f.value
                  ? "bg-brand-elevated text-brand-text"
                  : "text-brand-muted hover:text-brand-text"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-brand-border bg-brand-bg">
        <span className="w-3.5" />
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest w-36 shrink-0">Timestamp</span>
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest w-44 shrink-0">Worker</span>
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest flex-1">Action</span>
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest w-20 text-right shrink-0">Amount</span>
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest w-20 text-center shrink-0">Decision</span>
        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest w-28 shrink-0 hidden lg:block">Trace ID</span>
      </div>

      {filtered.map((entry) => (
        <AuditTraceExpand key={entry.id} entry={entry} />
      ))}

      {filtered.length === 0 && (
        <div className="px-5 py-8 text-center text-brand-muted font-mono text-sm">
          No entries for this filter.
        </div>
      )}
    </div>
  );
}
