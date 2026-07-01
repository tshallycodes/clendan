'use client'

import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

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
          <p className={`text-xl font-heading font-bold mt-1 ${unmatchedPct > 0.2 ? 'text-[#ff4d6d]' : 'text-[#00C853]'}`}>
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

function CategoriseAndMatchTrace({ trace }: { trace: Record<string, unknown> }) {
  const results = (trace.results as Array<{
    transaction_id: string
    ai_category: string
    matched_invoice_id: string | null
    confidence: number
    reasoning: string
  }>) || []
  const policyViolations = (trace.policy_violations as string[]) || []
  const categoryDistribution = (trace.category_distribution as Record<string, number>) || {}
  const categoryShifts = (trace.category_shifts as Array<{
    category: string
    change_pct: number
    current: number
    prior: number
  }>) || []
  const hasSignificantShifts = trace.has_significant_shifts as boolean
  const overallReasoning = trace.reasoning as string

  const matchedCount = results.filter(r => r.matched_invoice_id).length
  const avgConfidence = results.length > 0
    ? results.reduce((acc, r) => acc + r.confidence, 0) / results.length
    : 0

  const sc = policyViolations.length > 0
    ? { label: 'Blocked — policy violations',    color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' }
    : hasSignificantShifts
      ? { label: 'Categorised — shifts detected', color: 'text-[#f5a623]', bg: 'bg-[rgba(245,166,35,0.08)]', border: 'border-[rgba(245,166,35,0.2)]' }
      : { label: 'Categorised',                   color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',  border: 'border-[rgba(0,200,83,0.2)]' }

  return (
    <div className="space-y-4 pt-2">
      <div className={`inline-flex px-3 py-1.5 rounded-sm border ${sc.bg} ${sc.border}`}>
        <span className={`text-xs font-body font-medium ${sc.color}`}>{sc.label}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Transactions</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">{results.length}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Invoices matched</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">{matchedCount}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Avg confidence</p>
          <p className={`text-xl font-heading font-bold mt-1 ${avgConfidence >= 0.9 ? 'text-[#00C853]' : 'text-brand-text'}`}>
            {Math.round(avgConfidence * 100)}%
          </p>
        </div>
      </div>

      {Object.keys(categoryDistribution).length > 0 && (
        <div>
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1.5">Categories</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(categoryDistribution).map(([cat, count]) => (
              <span key={cat} className="text-[11px] font-body text-brand-secondary bg-brand-bg border border-brand-border rounded-sm px-2 py-0.5">
                {cat.replace(/_/g, ' ')} · {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {overallReasoning && (() => {
        let parsed: unknown = null
        try { parsed = JSON.parse(overallReasoning) } catch { /* plain text */ }
        return parsed != null ? (
          <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
            <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1.5">Reasoning</p>
            <pre className="text-[11px] font-body text-brand-secondary whitespace-pre-wrap overflow-x-auto max-h-48">
              {JSON.stringify(parsed, null, 2)}
            </pre>
          </div>
        ) : (
          <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
            <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1.5">Reasoning</p>
            <p className="text-[12px] font-body text-brand-secondary leading-relaxed">{overallReasoning}</p>
          </div>
        )
      })()}

      {policyViolations.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d]">Policy violations · {policyViolations.length}</p>
          {policyViolations.map((v, i) => (
            <div key={i} className="bg-[rgba(255,77,109,0.04)] border border-[rgba(255,77,109,0.15)] rounded-sm px-3 py-2.5">
              <p className="text-[12px] font-body text-brand-secondary">{v}</p>
            </div>
          ))}
        </div>
      )}

      {categoryShifts.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#f5a623]">Category shifts · {categoryShifts.length}</p>
          {categoryShifts.map((s, i) => (
            <div key={i} className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.2)] rounded-sm px-3 py-2.5 flex items-center justify-between">
              <span className="text-[12px] font-body text-brand-secondary">{s.category.replace(/_/g, ' ')}</span>
              <span className={`text-[12px] font-body font-medium ${s.change_pct > 0 ? 'text-[#f5a623]' : 'text-[#ff4d6d]'}`}>
                {s.change_pct > 0 ? '+' : ''}{s.change_pct}% ({s.prior} → {s.current})
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PayrollRecTrace({ trace }: { trace: Record<string, unknown> }) {
  const status = (trace.status as string) || 'clean'
  const period = trace.period as string
  const matchedCount = (trace.matched_count as number) ?? 0
  const missingCount = (trace.missing_count as number) ?? 0
  const ghostCount = (trace.ghost_count as number) ?? 0
  const discrepancyCount = (trace.discrepancy_count as number) ?? 0
  const totalPayrollMinor = (trace.total_payroll_minor as number) ?? 0
  const durationMs = trace.duration_ms as number

  const statusConfig = {
    clean:   { label: 'Clean — no issues found',      color: 'text-[#00C853]', bg: 'bg-[rgba(0,200,83,0.08)]',   border: 'border-[rgba(0,200,83,0.2)]' },
    flagged: { label: 'Flagged — review required',     color: 'text-[#f5a623]', bg: 'bg-[rgba(245,166,35,0.08)]', border: 'border-[rgba(245,166,35,0.2)]' },
    blocked: { label: 'Blocked — too many missing',    color: 'text-[#ff4d6d]', bg: 'bg-[rgba(255,77,109,0.08)]', border: 'border-[rgba(255,77,109,0.2)]' },
  }
  const sc = statusConfig[status as keyof typeof statusConfig] ?? statusConfig.clean

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center gap-3 flex-wrap">
        <div className={`inline-flex px-3 py-1.5 rounded-sm border ${sc.bg} ${sc.border}`}>
          <span className={`text-xs font-body font-medium ${sc.color}`}>{sc.label}</span>
        </div>
        {period && (
          <span className="text-[11px] font-body text-brand-muted">Period: {period}</span>
        )}
      </div>

      <div className="grid grid-cols-4 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Matched</p>
          <p className={`text-xl font-heading font-bold mt-1 ${matchedCount > 0 ? 'text-[#00C853]' : 'text-brand-text'}`}>{matchedCount}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Missing</p>
          <p className={`text-xl font-heading font-bold mt-1 ${missingCount > 0 ? 'text-[#ff4d6d]' : 'text-brand-text'}`}>
            {missingCount}
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Ghosts</p>
          <p className={`text-xl font-heading font-bold mt-1 ${ghostCount > 0 ? 'text-[#f5a623]' : 'text-brand-text'}`}>
            {ghostCount}
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Discrepancies</p>
          <p className={`text-xl font-heading font-bold mt-1 ${discrepancyCount > 0 ? 'text-[#f5a623]' : 'text-brand-text'}`}>
            {discrepancyCount}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-6 text-[11px] font-body text-brand-muted">
        {totalPayrollMinor > 0 && (
          <span>Total payroll: {(totalPayrollMinor / 100).toLocaleString('en-GB', { minimumFractionDigits: 2 })}</span>
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

function TraceView({ entry }: { entry: AuditEntry }) {
  const [showRaw, setShowRaw] = useState(false)
  const trace = typeof entry.reasoning_trace_json === 'object' ? entry.reasoning_trace_json : null
  const isApproval = entry.action === 'approval_approved' || entry.action === 'approval_rejected'
  const isReconciliation = !isApproval && entry.action?.startsWith('reconciliation:') && trace && 'overall_decision' in trace
  const isDocumentIntelligence = !isApproval && !isReconciliation && entry.action?.startsWith('document_processed:') && trace != null
  const isPayrollRec = !isApproval && !isReconciliation && !isDocumentIntelligence && entry.action === 'payroll_reconciliation:run' && trace != null
  const isCategoriseAndMatch = !isApproval && !isReconciliation && !isDocumentIntelligence && !isPayrollRec && entry.action === 'ai_accountant:categorise_and_match' && trace != null
  const isOrchestrator = !isApproval && !isReconciliation && !isDocumentIntelligence && !isPayrollRec && !isCategoriseAndMatch && trace && 'decision' in trace

  const hasFormatted = isApproval || isReconciliation || isDocumentIntelligence || isPayrollRec || isCategoriseAndMatch || isOrchestrator

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
            : isDocumentIntelligence
              ? <DocumentIntelligenceTrace trace={trace!} />
              : isPayrollRec
                ? <PayrollRecTrace trace={trace!} />
                : isCategoriseAndMatch
                  ? <CategoriseAndMatchTrace trace={trace!} />
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

export function ToolAuditTab({ toolId }: { toolId: string | null }) {
  const { getToken } = useAuth()
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
          setEntries(json.data?.entries ?? [])
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [toolId, getToken])

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
                  <TraceView entry={e} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
