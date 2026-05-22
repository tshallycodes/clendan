"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";
import type { AuditEntry } from "@/lib/mock-data";

const DECISION_STYLES: Record<AuditEntry["decision"], string> = {
  AUTO: "bg-[rgba(0,200,83,0.08)] text-brand-green border-[rgba(0,200,83,0.2)]",
  APPROVE: "bg-[rgba(0,200,83,0.08)] text-brand-green border-[rgba(0,200,83,0.2)]",
  FLAG: "bg-[rgba(245,166,35,0.08)] text-brand-warning border-[rgba(245,166,35,0.2)]",
  REJECT: "bg-[rgba(255,77,109,0.08)] text-brand-danger border-[rgba(255,77,109,0.2)]",
};

interface AuditTraceExpandProps {
  entry: AuditEntry;
}

export function AuditTraceExpand({ entry }: AuditTraceExpandProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-brand-border last:border-0">
      <div
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-brand-elevated transition-colors"
      >
        <ChevronRight
          className={cn("w-3.5 h-3.5 text-brand-muted transition-transform shrink-0", expanded && "rotate-90")}
        />
        <span className="text-xs font-mono text-brand-muted w-36 shrink-0">{entry.timestamp}</span>
        <span className="text-xs font-mono text-brand-muted w-44 shrink-0 truncate">{entry.worker}</span>
        <span className="text-xs font-mono text-brand-text flex-1 truncate">{entry.action}</span>
        {entry.amount && (
          <span className="text-xs font-mono text-brand-text w-20 text-right shrink-0">
            {formatCurrency(entry.amount, entry.currency)}
          </span>
        )}
        <span
          className={cn(
            "text-[10px] font-mono px-2 py-0.5 rounded-sm border w-20 text-center shrink-0",
            DECISION_STYLES[entry.decision]
          )}
        >
          {entry.decision}
        </span>
        <span className="text-[10px] font-mono text-brand-muted w-28 shrink-0 hidden lg:block">{entry.traceId}</span>
      </div>
      {expanded && (
        <div className="px-4 pb-4 ml-6">
          <pre className="text-xs font-mono text-brand-muted bg-[#0d0d14] border border-brand-border rounded-sm p-4 whitespace-pre-wrap leading-relaxed">
            {entry.fullTrace}
          </pre>
        </div>
      )}
    </div>
  );
}
