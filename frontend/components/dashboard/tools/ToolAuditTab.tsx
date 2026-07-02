'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface AuditEntry {
  id: string
  actor: string
  action: string
  model_version: string
  created_at: string
  execution_id: string | null
  reasoning_trace_json: Record<string, unknown> | string | null
}

interface Assessment {
  action: 'flag' | 'review' | 'ok'
  item_id: string
  severity: 'high' | 'medium' | 'low'
  item_type: string
  reasoning: string
}

function ReconciliationTrace({ trace }: { trace: Record<string, unknown> }) {
  const decision = trace.overall_decision as string
  const policyBreach = trace.policy_breach as boolean
  const txnCount = (trace.transaction_count as number) || 0
  const matchedTxns = (trace.matched_transactions as number) || 0
  const unmatchedTxns = (trace.unmatched_transactions as number) || 0
  const billCount = (trace.bill_count as number) || 0
  const unmatchedBills = (trace.unmatched_bills as number) || 0
  const invoiceCount = (trace.invoice_count as number) || 0
  const unmatchedInvoices = (trace.unmatched_invoices as number) || 0
  const unmatchedPct = (trace.unmatched_pct as number) || 0
  const policy = (trace.policy as Record<string, number>) ?? {}
  const unmatchedPctThreshold = policy.unmatched_pct_threshold ?? 0.20
  const assessments = (trace.claude_assessments as Assessment[]) || []
  const flagged = assessments.filter(a => a.action === 'flag')
  const reviews = assessments.filter(a => a.action === 'review')

  const decisionConfig = {
    flagged:           { label: 'Flagged — issues found',  color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
    approval_required: { label: 'Approval required',       color: 'text-[#00a8cc]', bg: 'bg-[rgba(0,168,204,0.08)]', border: 'border-[rgba(0,168,204,0.2)]' },
    auto_approved:     { label: 'Auto-approved',           color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',  border: 'border-[rgba(0,200,83,0.2)]' },
  }
  const dc = decisionConfig[decision as keyof typeof decisionConfig] ?? decisionConfig.auto_approved

  return (
    <div className="space-y-4 pt-2">
      <div className={`inline-flex px-3 py-1.5 rounded-sm border ${dc.bg} ${dc.border}`}>
        <span className={`text-xs font-body font-medium ${dc.color}`}>{dc.label}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Transactions reviewed</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">{txnCount}</p>
          <p className="text-[11px] font-body text-brand-muted mt-0.5">{matchedTxns} matched · {unmatchedTxns} unmatched</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Bills / Invoices</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">{billCount + invoiceCount}</p>
          <p className="text-[11px] font-body text-brand-muted mt-0.5">
            {unmatchedBills + unmatchedInvoices} unmatched
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Unmatched rate</p>
          <p className={`text-xl font-heading font-bold mt-1 ${unmatchedPct > unmatchedPctThreshold ? 'text-[#ff4d6d]' : 'text-[#00C853]'}`}>
            {Math.round(unmatchedPct * 100)}%
          </p>
          <p className="text-[11px] font-body text-brand-muted mt-0.5">
            {policyBreach ? 'Policy threshold exceeded' : 'Within policy'}
          </p>
        </div>
      </div>

      {flagged.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d]">
            Flagged items · {flagged.length}
          </p>
          {flagged.map((a, i) => (
            <div key={i} className="bg-[rgba(255,77,109,0.04)] border border-[rgba(255,77,109,0.15)] rounded-sm px-3 py-2.5">
              <p className="text-[12px] font-body text-brand-secondary leading-relaxed">{a.reasoning}</p>
              <p className="text-[11px] font-body text-brand-muted mt-1 capitalize">{a.item_type} · {a.severity} severity</p>
            </div>
          ))}
        </div>
      )}

      {reviews.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#00a8cc]">
            Needs review · {reviews.length}
          </p>
          {reviews.map((a, i) => (
            <div key={i} className="bg-[rgba(0,168,204,0.04)] border border-[rgba(0,168,204,0.15)] rounded-sm px-3 py-2.5">
              <p className="text-[12px] font-body text-brand-secondary leading-relaxed">{a.reasoning}</p>
              <p className="text-[11px] font-body text-brand-muted mt-1 capitalize">{a.item_type} · {a.severity} severity</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DocumentIntelligenceTrace({ trace }: { trace: Record<string, unknown> }) {
  const decision = (trace.decision as string) || 'approval_required'
  const documentType = (trace.document_type as string) || 'invoice'
  const confidence = trace.confidence as number
  const flags = (trace.flags as string[]) || []
  const reason = trace.reason as string
  const decisionConfig = {
    auto_approved:         { label: 'Auto-approved',      color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
    analysed:              { label: 'Analysed',           color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
    approval_required:     { label: 'Approval required',  color: 'text-[#00a8cc]', bg: 'bg-[rgba(0,168,204,0.08)]', border: 'border-[rgba(0,168,204,0.2)]' },
    blocked:               { label: 'Blocked',            color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
    classification_failed: { label: 'Unreadable',         color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  }
  const dc = decisionConfig[decision as keyof typeof decisionConfig] ?? { label: decision, color: 'text-brand-muted', bg: 'bg-brand-bg', border: 'border-brand-border' }

  return (
    <div className="space-y-4 pt-2">
      <div className={`inline-flex px-3 py-1.5 rounded-sm border ${dc.bg} ${dc.border}`}>
        <span className={`text-xs font-body font-medium ${dc.color}`}>{dc.label}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Confidence</p>
          <p className={`text-xl font-heading font-bold mt-1 ${(confidence ?? 0) >= 0.9 ? 'text-[#00C853]' : 'text-brand-text'}`}>
            {confidence != null ? `${Math.round(confidence * 100)}%` : '—'}
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Document type</p>
          <p className="text-xs font-body text-brand-text mt-1 capitalize">{documentType.replace(/_/g, ' ') || '—'}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Policy flags</p>
          <p className={`text-xl font-heading font-bold mt-1 ${flags.length > 0 ? 'text-[#f5a623]' : 'text-[#00C853]'}`}>
            {flags.length}
          </p>
        </div>
      </div>

      {reason && (
        <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1.5">Reason</p>
          <p className="text-[12px] font-body text-brand-secondary leading-relaxed">{reason}</p>
        </div>
      )}

      {flags.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#f5a623]">Policy flags</p>
          {flags.map((flag, i) => (
            <div key={i} className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.2)] rounded-sm px-3 py-2.5">
              <p className="text-[12px] font-body text-brand-secondary leading-relaxed">{flag}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PayrollRecTrace({ trace, executionId, getToken, currencySymbol }: { trace: Record<string, unknown>; executionId: string | null; getToken: () => Promise<string | null>; currencySymbol: string }) {
  const status = (trace.status as string) || 'clean'
  const period = trace.period as string
  const rosterSize = (trace.roster_size as number) ?? 0
  const matchedCount = (trace.matched_count as number) ?? 0
  const missingCount = (trace.missing_count as number) ?? 0
  const ghostCount = (trace.ghost_count as number) ?? 0
  const discrepancyCount = (trace.discrepancy_count as number) ?? 0
  const totalPayrollMinor = (trace.total_payroll_minor as number) ?? 0
  const durationMs = trace.duration_ms as number

  const traceMissingList = (trace.missing as Array<{ name: string; expected_minor: number }>) || []
  const traceGhostList = (trace.ghosts as Array<{ name: string; amount_minor: number }>) || []
  const traceDiscrepancyList = (trace.discrepancies as Array<{ name: string; expected_minor: number; actual_minor: number; diff_pct: number }>) || []

  const needsFetch = traceMissingList.length === 0 && traceGhostList.length === 0 && traceDiscrepancyList.length === 0
    && (missingCount > 0 || ghostCount > 0 || discrepancyCount > 0)

  const [fetched, setFetched] = useState<{ missing: typeof traceMissingList; ghosts: typeof traceGhostList; discrepancies: typeof traceDiscrepancyList } | null>(null)

  const fetchDetails = useCallback(async () => {
    if (!executionId) return
    try {
      const token = await getToken()
      const res = await fetch(`${API}/payroll-runs/by-execution/${executionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const json = await res.json()
        setFetched({
          missing: json.data?.missing ?? [],
          ghosts: json.data?.ghosts ?? [],
          discrepancies: json.data?.discrepancies ?? [],
        })
      }
    } catch { /* silent — detail is optional */ }
  }, [executionId, getToken])

  useEffect(() => {
    if (needsFetch) fetchDetails()
  }, [needsFetch, fetchDetails])

  const missingList = traceMissingList.length > 0 ? traceMissingList : (fetched?.missing ?? [])
  const ghostList = traceGhostList.length > 0 ? traceGhostList : (fetched?.ghosts ?? [])
  const discrepancyList = traceDiscrepancyList.length > 0 ? traceDiscrepancyList : (fetched?.discrepancies ?? [])

  const missingPct = rosterSize > 0 ? Math.round((missingCount / rosterSize) * 100) : 0

  const statusConfig = {
    clean:   { label: 'Clean — no issues found',   color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
    flagged: { label: 'Flagged — review required',  color: 'text-[#f5a623]', bg: 'bg-[rgba(245,166,35,0.08)]', border: 'border-[rgba(245,166,35,0.2)]' },
    blocked: { label: 'Blocked — too many missing', color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  }
  const sc = statusConfig[status as keyof typeof statusConfig] ?? statusConfig.clean

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center gap-3 flex-wrap">
        <div className={`inline-flex px-3 py-1.5 rounded-sm border ${sc.bg} ${sc.border}`}>
          <span className={`text-xs font-body font-medium ${sc.color}`}>{sc.label}</span>
        </div>
        {period && <span className="text-[11px] font-body text-brand-muted">Period: {period}</span>}
        {rosterSize > 0 && <span className="text-[11px] font-body text-brand-muted">Roster: {rosterSize} employees</span>}
      </div>

      <div className="grid grid-cols-4 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Matched</p>
          <p className={`text-xl font-heading font-bold mt-1 ${matchedCount > 0 ? 'text-[#00C853]' : 'text-brand-text'}`}>{matchedCount}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Missing</p>
          <p className={`text-xl font-heading font-bold mt-1 ${missingCount > 0 ? 'text-[#ff4d6d]' : 'text-brand-text'}`}>{missingCount}</p>
          {missingCount > 0 && rosterSize > 0 && (
            <p className="text-[10px] font-body text-brand-muted mt-0.5">{missingPct}% of roster · blocks above 30%</p>
          )}
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Ghosts</p>
          <p className={`text-xl font-heading font-bold mt-1 ${ghostCount > 0 ? 'text-[#f5a623]' : 'text-brand-text'}`}>{ghostCount}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Discrepancies</p>
          <p className={`text-xl font-heading font-bold mt-1 ${discrepancyCount > 0 ? 'text-[#f5a623]' : 'text-brand-text'}`}>{discrepancyCount}</p>
        </div>
      </div>

      {missingList.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d]">Missing employees · {missingList.length}</p>
          {missingList.map((m, i) => (
            <div key={i} className="bg-[rgba(255,77,109,0.04)] border border-[rgba(255,77,109,0.15)] rounded-sm px-3 py-2.5 flex items-center justify-between">
              <span className="text-[12px] font-body text-brand-secondary">{m.name}</span>
              <span className="text-[11px] font-body text-brand-muted">Expected: {currencySymbol}{(m.expected_minor / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })}</span>
            </div>
          ))}
        </div>
      )}

      {ghostList.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#f5a623]">Ghost employees · {ghostList.length}</p>
          {ghostList.map((g, i) => (
            <div key={i} className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.2)] rounded-sm px-3 py-2.5 flex items-center justify-between">
              <span className="text-[12px] font-body text-brand-secondary">{g.name}</span>
              <span className="text-[11px] font-body text-brand-muted">Amount: {currencySymbol}{(g.amount_minor / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })}</span>
            </div>
          ))}
        </div>
      )}

      {discrepancyList.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#f5a623]">Salary discrepancies · {discrepancyList.length}</p>
          {discrepancyList.map((d, i) => (
            <div key={i} className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.2)] rounded-sm px-3 py-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-body text-brand-secondary">{d.name}</span>
                <span className="text-[12px] font-body font-medium text-[#f5a623]">+{d.diff_pct}% off</span>
              </div>
              <p className="text-[11px] font-body text-brand-muted mt-0.5">
                Expected: {currencySymbol}{(d.expected_minor / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })} · Actual: {currencySymbol}{(d.actual_minor / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-6 text-[11px] font-body text-brand-muted">
        {totalPayrollMinor > 0 && (
          <span>Total payroll: {currencySymbol}{(totalPayrollMinor / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })}</span>
        )}
        {durationMs != null && <span>Duration: {durationMs}ms</span>}
      </div>
    </div>
  )
}

const DECISION_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  routed:            { label: 'Routed to tool',      color: 'text-[#00a8cc]', bg: 'bg-[rgba(0,168,204,0.08)]',  border: 'border-[rgba(0,168,204,0.2)]' },
  auto_approved:     { label: 'Auto-approved',        color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
  approval_required: { label: 'Approval required',    color: 'text-[#00a8cc]', bg: 'bg-[rgba(0,168,204,0.08)]',  border: 'border-[rgba(0,168,204,0.2)]' },
  blocked:           { label: 'Blocked',              color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  flagged:           { label: 'Flagged',              color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
}

function OrchestratorTrace({ trace }: { trace: Record<string, unknown> }) {
  const decision = (trace.decision as string) || 'routed'
  const reasoning = trace.reasoning as string
  const confidence = trace.confidence as number
  const eventType = trace.event_type as string
  const durationMs = trace.duration_ms as number
  const payloadKeys = (trace.payload_keys as string[]) || []
  const dc = DECISION_CONFIG[decision] ?? DECISION_CONFIG.routed

  return (
    <div className="space-y-4 pt-2">
      <div className={`inline-flex px-3 py-1.5 rounded-sm border ${dc.bg} ${dc.border}`}>
        <span className={`text-xs font-body font-medium ${dc.color}`}>{dc.label}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Event type</p>
          <p className="text-xs font-body text-brand-text mt-1">{eventType ?? '—'}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Confidence</p>
          <p className={`text-xl font-heading font-bold mt-1 ${(confidence ?? 0) >= 0.9 ? 'text-[#00C853]' : 'text-brand-text'}`}>
            {confidence != null ? `${Math.round(confidence * 100)}%` : '—'}
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Duration</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">
            {durationMs != null ? `${durationMs}ms` : '—'}
          </p>
        </div>
      </div>

      {reasoning && (
        <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1.5">Reasoning</p>
          <p className="text-[12px] font-body text-brand-secondary leading-relaxed">{reasoning}</p>
        </div>
      )}

      {payloadKeys.length > 0 && (
        <div>
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1.5">Payload fields</p>
          <div className="flex flex-wrap gap-1.5">
            {payloadKeys.map(k => (
              <span key={k} className="text-[11px] font-body text-brand-secondary bg-brand-bg border border-brand-border rounded-sm px-2 py-0.5">{k}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ApprovalTrace({ entry, trace }: { entry: AuditEntry; trace: Record<string, unknown> }) {
  const isApproved = entry.action === 'approval_approved'
  const actor = entry.actor.startsWith('user:') ? entry.actor.slice(5) : entry.actor
  const approvalId = trace.approval_id as string | undefined
  const executionId = trace.execution_id as string | undefined

  const dc = isApproved
    ? { label: 'Approved', color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]', border: 'border-[rgba(0,200,83,0.2)]' }
    : { label: 'Rejected', color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' }

  return (
    <div className="space-y-4 pt-2">
      <div className={`inline-flex px-3 py-1.5 rounded-sm border ${dc.bg} ${dc.border}`}>
        <span className={`text-xs font-body font-medium ${dc.color}`}>{dc.label}</span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Actioned by</p>
          <p className="text-xs font-body text-brand-text mt-1 truncate">{actor}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Action</p>
          <p className={`text-xs font-body font-medium mt-1 ${dc.color}`}>{isApproved ? 'Approved' : 'Rejected'}</p>
        </div>
      </div>

      {approvalId && (
        <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1">Approval ID</p>
          <p className="text-[11px] font-body text-brand-muted break-all">{approvalId}</p>
        </div>
      )}
      {executionId && (
        <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1">Execution</p>
          <p className="text-[11px] font-body text-brand-muted break-all">{executionId}</p>
        </div>
      )}
    </div>
  )
}

function fmtCents(cents: number | null | undefined, symbol: string) {
  if (cents == null) return `${symbol}0.00`
  return `${symbol}${(cents / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtPeriod(start: string, end: string) {
  const fmt = (s: string) => new Date(s).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
  return `${fmt(start)} – ${fmt(end)}`
}

function AuditStatGrid({ stats }: { stats: { label: string; value: string; danger?: boolean }[] }) {
  return (
    <div className={`grid gap-2 grid-cols-${Math.min(stats.length, 4)}`}>
      {stats.map(s => (
        <div key={s.label} className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">{s.label}</p>
          <p className={`text-xl font-heading font-bold mt-1 ${s.danger ? 'text-[#ff4d6d]' : 'text-brand-text'}`}>{s.value}</p>
        </div>
      ))}
    </div>
  )
}

function InvoiceRecAuditTrace({ trace, currencySymbol }: { trace: Record<string, unknown>; currencySymbol: string }) {
  const start = trace.period_start as string
  const end = trace.period_end as string
  const source = trace.source as string
  const total = (trace.total_invoices as number) ?? 0
  const paid = (trace.paid_count as number) ?? 0
  const overdue = (trace.overdue_count as number) ?? 0
  const flagged = (trace.flagged_count as number) ?? 0
  const amount = trace.total_amount_cents as number
  const outstanding = trace.total_outstanding_cents as number
  const tax = trace.total_tax_cents as number

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="inline-flex px-3 py-1.5 rounded-sm border bg-[rgba(245,166,35,0.08)] border-[rgba(245,166,35,0.2)]">
          <span className="text-xs font-body font-medium text-[#f5a623]">Invoice reconciliation</span>
        </div>
        {start && end && <span className="text-[11px] font-body text-brand-muted">{fmtPeriod(start, end)}</span>}
        {source && source !== 'all' && <span className="text-[11px] font-body text-brand-muted capitalize">Source: {source}</span>}
      </div>
      <AuditStatGrid stats={[
        { label: 'Total invoices', value: String(total) },
        { label: 'Paid', value: String(paid) },
        { label: 'Overdue', value: String(overdue), danger: overdue > 0 },
        { label: 'Flagged', value: String(flagged), danger: flagged > 0 },
      ]} />
      <AuditStatGrid stats={[
        { label: 'Total amount', value: fmtCents(amount, currencySymbol) },
        { label: 'Outstanding', value: fmtCents(outstanding, currencySymbol), danger: outstanding > 0 },
        { label: 'Tax collected', value: fmtCents(tax, currencySymbol) },
      ]} />
    </div>
  )
}

function VatRecAuditTrace({ trace, currencySymbol }: { trace: Record<string, unknown>; currencySymbol: string }) {
  const start = trace.period_start as string
  const end = trace.period_end as string
  const source = trace.source as string
  const total = (trace.total_invoices as number) ?? 0
  const outputVat = trace.output_vat_cents as number
  const netSales = trace.net_sales_cents as number
  const vatPosition = trace.vat_position_cents as number
  const flagged = (trace.flagged_count as number) ?? 0
  const rate = trace.expected_vat_rate_pct as number

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="inline-flex px-3 py-1.5 rounded-sm border bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]">
          <span className="text-xs font-body font-medium text-[#00C853]">VAT reconciliation</span>
        </div>
        {start && end && <span className="text-[11px] font-body text-brand-muted">{fmtPeriod(start, end)}</span>}
        {source && source !== 'all' && <span className="text-[11px] font-body text-brand-muted capitalize">Source: {source}</span>}
        {rate != null && <span className="text-[11px] font-body text-brand-muted">Expected rate: {rate}%</span>}
      </div>
      <AuditStatGrid stats={[
        { label: 'Output VAT', value: fmtCents(outputVat, currencySymbol) },
        { label: 'Net sales', value: fmtCents(netSales, currencySymbol) },
        { label: 'VAT position', value: fmtCents(vatPosition, currencySymbol) },
        { label: 'Total invoices', value: String(total) },
      ]} />
      {flagged > 0 && (
        <div className="bg-[rgba(255,77,109,0.04)] border border-[rgba(255,77,109,0.15)] rounded-sm px-3 py-2.5">
          <p className="text-[12px] font-body text-[#ff4d6d]">{flagged} invoice{flagged !== 1 ? 's' : ''} flagged — missing or unexpected VAT rate</p>
        </div>
      )}
    </div>
  )
}

function TraceView({ entry, getToken, currencySymbol }: { entry: AuditEntry; getToken: () => Promise<string | null>; currencySymbol: string }) {
  const [showRaw, setShowRaw] = useState(false)
  const trace = typeof entry.reasoning_trace_json === 'object' ? entry.reasoning_trace_json : null
  const isApproval = entry.action === 'approval_approved' || entry.action === 'approval_rejected'
  const isReconciliation = !isApproval && entry.action?.startsWith('bank_reconciliation:') && trace && 'overall_decision' in trace
  const isInvoiceRec = !isApproval && entry.action === 'invoice_reconciliation:run' && trace != null
  const isVatRec = !isApproval && entry.action === 'vat_reconciliation:run' && trace != null
  const isDocumentIntelligence = !isApproval && !isReconciliation && !isInvoiceRec && !isVatRec && entry.action?.startsWith('document_processed:') && trace != null
  const isPayrollRec = !isApproval && !isReconciliation && !isInvoiceRec && !isVatRec && !isDocumentIntelligence && entry.action === 'payroll_reconciliation:run' && trace != null
  const isOrchestrator = !isApproval && !isReconciliation && !isInvoiceRec && !isVatRec && !isDocumentIntelligence && !isPayrollRec && trace && 'decision' in trace

  const hasFormatted = isApproval || isReconciliation || isInvoiceRec || isVatRec || isDocumentIntelligence || isPayrollRec || isOrchestrator

  return (
    <div className="space-y-2">
      {hasFormatted && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setShowRaw(v => !v)}
            className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors"
          >
            {showRaw ? 'Show summary' : 'View raw'}
          </button>
        </div>
      )}
      {hasFormatted && !showRaw ? (
        isApproval
          ? <ApprovalTrace entry={entry} trace={trace ?? {}} />
          : isReconciliation
            ? <ReconciliationTrace trace={trace!} />
            : isInvoiceRec
              ? <InvoiceRecAuditTrace trace={trace!} currencySymbol={currencySymbol} />
              : isVatRec
                ? <VatRecAuditTrace trace={trace!} currencySymbol={currencySymbol} />
                : isDocumentIntelligence
                  ? <DocumentIntelligenceTrace trace={trace!} />
                  : isPayrollRec
                    ? <PayrollRecTrace trace={trace!} executionId={entry.execution_id} getToken={getToken} currencySymbol={currencySymbol} />
                    : <OrchestratorTrace trace={trace!} />
      ) : (
        entry.reasoning_trace_json && (
          <pre className="text-[11px] font-body text-brand-secondary whitespace-pre-wrap bg-brand-bg border border-brand-border rounded-sm p-3 overflow-x-auto max-h-64">
            {typeof entry.reasoning_trace_json === 'object'
              ? JSON.stringify(entry.reasoning_trace_json, null, 2)
              : entry.reasoning_trace_json}
          </pre>
        )
      )}
    </div>
  )
}

export function ToolAuditTab({ toolId, initialAction }: { toolId: string | null; initialAction?: string }) {
  const { getToken } = useAuth()
  const { currency } = useCurrency()
  const currencySymbol = CURRENCY_MAP[currency]?.symbol ?? currency
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!toolId) return
    async function load() {
      setLoading(true)
      try {
        const token = await getToken()
        const res = await fetch(`${API}/dashboard/audit?tool_id=${toolId}&limit=50`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          const loaded: AuditEntry[] = json.data?.entries ?? []
          setEntries(loaded)
          if (initialAction) {
            const match = loaded.find(e => e.action?.startsWith(initialAction))
            if (match) setExpanded(match.id)
          }
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [toolId, getToken, initialAction])

  const filtered = useMemo(() => {
    if (!search) return entries
    const q = search.toLowerCase()
    return entries.filter(e =>
      e.actor.toLowerCase().includes(q) ||
      e.action.toLowerCase().includes(q) ||
      (e.execution_id ?? '').toLowerCase().includes(q),
    )
  }, [entries, search])

  if (loading) {
    return <div className="py-12 text-center text-xs font-body text-brand-muted">Loading…</div>
  }

  return (
    <div className="space-y-3">
      <input
        type="text"
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search by actor, action…"
        className="w-full max-w-xs bg-brand-bg border border-brand-border focus:border-[#00C853] rounded-sm px-3 py-1.5 text-xs font-body text-brand-text placeholder:text-brand-muted outline-none transition-colors"
      />

      {filtered.length === 0 ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
          <p className="text-xs font-body text-brand-muted">
            {search ? 'No entries match your search' : 'No audit entries yet'}
          </p>
        </div>
      ) : (
        <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
          {filtered.map((e, i) => (
            <div key={e.id} className={i > 0 ? 'border-t border-brand-border' : ''}>
              <button
                type="button"
                onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-brand-elevated transition-colors text-left"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <span className="text-[11px] font-body text-brand-muted shrink-0">
                    {new Date(e.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="text-xs font-body text-brand-secondary truncate">{e.action}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <span className="text-[11px] font-body text-brand-muted">{e.actor}</span>
                  <span className="text-[11px] font-body text-brand-muted">{expanded === e.id ? '▲' : '▼'}</span>
                </div>
              </button>
              {expanded === e.id && (
                <div className="px-4 pb-4 space-y-2 border-t border-brand-border">
                  {e.execution_id && (
                    <p className="text-[11px] font-body text-brand-muted pt-2">execution: {e.execution_id}</p>
                  )}
                  {e.model_version && (
                    <p className="text-[11px] font-body text-brand-muted">model: {e.model_version}</p>
                  )}
                  <TraceView entry={e} getToken={getToken} currencySymbol={currencySymbol} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
