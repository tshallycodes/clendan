"use client";

import { useState, useCallback } from "react";
import { Clock } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { MOCK_PENDING_APPROVALS, type PendingApproval } from "@/lib/mock-data";
import { ToastContainer, type ToastItem } from "@/components/ui/ToastNotification";

export function ApprovalsTab() {
  const [approvals, setApprovals] = useState<PendingApproval[]>(MOCK_PENDING_APPROVALS);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  function handleApprove(id: string, vendor: string) {
    setApprovals((prev) => prev.filter((a) => a.id !== id));
    setToasts((prev) => [
      ...prev,
      { id: `toast-${Date.now()}`, message: `Approved: ${vendor}`, type: "success" },
    ]);
  }

  function handleReject(id: string, vendor: string) {
    setApprovals((prev) => prev.filter((a) => a.id !== id));
    setToasts((prev) => [
      ...prev,
      { id: `toast-${Date.now()}`, message: `Rejected: ${vendor}`, type: "error" },
    ]);
  }

  return (
    <>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-brand-border flex items-center justify-between">
          <h3 className="font-heading font-semibold text-brand-text text-sm">Pending Approvals</h3>
          <span className="text-xs font-mono text-brand-muted">{approvals.length} waiting</span>
        </div>

        {approvals.length === 0 ? (
          <div className="px-5 py-12 text-center text-brand-muted font-mono text-sm">
            All caught up — no pending approvals.
          </div>
        ) : (
          <div className="divide-y divide-brand-border">
            {approvals.map((approval) => (
              <div key={approval.id} className="px-5 py-5 flex flex-col sm:flex-row sm:items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="font-heading font-semibold text-brand-text text-sm mb-0.5">{approval.vendor}</div>
                  <div className="text-xs font-mono text-brand-muted mb-1">
                    {approval.invoiceRef} · submitted by {approval.submittedBy.replace(" Worker", "")} Worker
                  </div>
                  <div className="flex items-center gap-1.5 text-xs font-mono text-brand-warning">
                    <Clock className="w-3 h-3" />
                    Waiting {approval.waitingMins} minutes
                  </div>
                </div>
                <div className="font-heading font-bold text-brand-text text-lg shrink-0">
                  {formatCurrency(approval.amount, approval.currency)}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => handleApprove(approval.id, approval.vendor)}
                    className="text-xs font-mono bg-brand-green text-black px-4 py-2 rounded-sm font-semibold hover:bg-[#00a844] transition-colors active:scale-[0.97]"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleReject(approval.id, approval.vendor)}
                    className="text-xs font-mono bg-[rgba(255,77,109,0.1)] border border-brand-danger text-brand-danger px-4 py-2 rounded-sm hover:bg-[rgba(255,77,109,0.15)] transition-colors"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
