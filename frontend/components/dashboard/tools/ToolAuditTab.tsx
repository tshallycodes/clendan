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
        <span className={`text-xs font-mono font-medium ${dc.color}`}>{dc.label}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Transactions reviewed</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">{txnCount}</p>
          <p className="text-[10px] font-mono text-brand-muted mt-0.5">{matchedTxns} matched · {unmatchedTxns} unmatched</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Bills / Invoices</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">{billCount + invoiceCount}</p>
          <p className="text-[10px] font-mono text-brand-muted mt-0.5">
            {unmatchedBills + unmatchedInvoices} unmatched
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Unmatched rate</p>
          <p className={`text-xl font-heading font-bold mt-1 ${unmatchedPct > 0.2 ? 'text-[#ff4d6d]' : 'text-[#00C853]'}`}>
            {Math.round(unmatchedPct * 100)}%
          </p>
          <p className="text-[10px] font-mono text-brand-muted mt-0.5">
            {policyBreach ? 'Policy threshold exceeded' : 'Within policy'}
          </p>
        </div>
      </div>

      {flagged.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#ff4d6d]">
            Flagged items · {flagged.length}
          </p>
          {flagged.map((a, i) => (
            <div key={i} className="bg-[rgba(255,77,109,0.04)] border border-[rgba(255,77,109,0.15)] rounded-sm px-3 py-2.5">
              <p className="text-[11px] font-mono text-brand-secondary leading-relaxed">{a.reasoning}</p>
              <p className="text-[10px] font-mono text-brand-muted mt-1 capitalize">{a.item_type} · {a.severity} severity</p>
            </div>
          ))}
        </div>
      )}

      {reviews.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#00a8cc]">
            Needs review · {reviews.length}
          </p>
          {reviews.map((a, i) => (
            <div key={i} className="bg-[rgba(0,168,204,0.04)] border border-[rgba(0,168,204,0.15)] rounded-sm px-3 py-2.5">
              <p className="text-[11px] font-mono text-brand-secondary leading-relaxed">{a.reasoning}</p>
              <p className="text-[10px] font-mono text-brand-muted mt-1 capitalize">{a.item_type} · {a.severity} severity</p>
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
        <span className={`text-xs font-mono font-medium ${dc.color}`}>{dc.label}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Confidence</p>
          <p className={`text-xl font-heading font-bold mt-1 ${(confidence ?? 0) >= 0.9 ? 'text-[#00C853]' : 'text-brand-text'}`}>
            {confidence != null ? `${Math.round(confidence * 100)}%` : '—'}
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Document type</p>
          <p className="text-xs font-mono text-brand-text mt-1 capitalize">{documentType.replace(/_/g, ' ') || '—'}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Policy flags</p>
          <p className={`text-xl font-heading font-bold mt-1 ${flags.length > 0 ? 'text-[#f5a623]' : 'text-[#00C853]'}`}>
            {flags.length}
          </p>
        </div>
      </div>

      {reason && (
        <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1.5">Reason</p>
          <p className="text-[11px] font-mono text-brand-secondary leading-relaxed">{reason}</p>
        </div>
      )}

      {flags.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#f5a623]">Policy flags</p>
          {flags.map((flag, i) => (
            <div key={i} className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.2)] rounded-sm px-3 py-2.5">
              <p className="text-[11px] font-mono text-brand-secondary leading-relaxed">{flag}</p>
            </div>
          ))}
        </div>
      )}
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
        <span className={`text-xs font-mono font-medium ${dc.color}`}>{dc.label}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Event type</p>
          <p className="text-xs font-mono text-brand-text mt-1">{eventType ?? '—'}</p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Confidence</p>
          <p className={`text-xl font-heading font-bold mt-1 ${(confidence ?? 0) >= 0.9 ? 'text-[#00C853]' : 'text-brand-text'}`}>
            {confidence != null ? `${Math.round(confidence * 100)}%` : '—'}
          </p>
        </div>
        <div className="bg-brand-bg border border-brand-border rounded-sm p-3">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Duration</p>
          <p className="text-xl font-heading font-bold text-brand-text mt-1">
            {durationMs != null ? `${durationMs}ms` : '—'}
          </p>
        </div>
      </div>

      {reasoning && (
        <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2.5">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1.5">Reasoning</p>
          <p className="text-[11px] font-mono text-brand-secondary leading-relaxed">{reasoning}</p>
        </div>
      )}

      {payloadKeys.length > 0 && (
        <div>
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1.5">Payload fields</p>
          <div className="flex flex-wrap gap-1.5">
            {payloadKeys.map(k => (
              <span key={k} className="text-[10px] font-mono text-brand-secondary bg-brand-bg border border-brand-border rounded-sm px-2 py-0.5">{k}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TraceView({ entry }: { entry: AuditEntry }) {
  const [showRaw, setShowRaw] = useState(false)
  const trace = typeof entry.reasoning_trace_json === 'object' ? entry.reasoning_trace_json : null
  const isReconciliation = entry.action?.startsWith('reconciliation:') && trace && 'overall_decision' in trace
  const isDocumentIntelligence = !isReconciliation && entry.action?.startsWith('document_processed:') && trace != null
  const isOrchestrator = !isReconciliation && !isDocumentIntelligence && trace && 'decision' in trace

  const hasFormatted = isReconciliation || isDocumentIntelligence || isOrchestrator

  return (
    <div className="space-y-2">
      {hasFormatted && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setShowRaw(v => !v)}
            className="text-[10px] font-mono text-brand-muted hover:text-brand-secondary transition-colors"
          >
            {showRaw ? 'Show summary' : 'View raw'}
          </button>
        </div>
      )}
      {hasFormatted && !showRaw ? (
        isReconciliation
          ? <ReconciliationTrace trace={trace!} />
          : isDocumentIntelligence
            ? <DocumentIntelligenceTrace trace={trace!} />
            : <OrchestratorTrace trace={trace!} />
      ) : (
        entry.reasoning_trace_json && (
          <pre className="text-[10px] font-mono text-brand-secondary whitespace-pre-wrap bg-brand-bg border border-brand-border rounded-sm p-3 overflow-x-auto max-h-64">
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
        const res = await fetch(`${API}/v1/dashboard/audit?tool_id=${toolId}&limit=50`, {
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
    return <div className="py-12 text-center text-xs font-mono text-brand-muted">Loading…</div>
  }

  return (
    <div className="space-y-3">
      <input
        type="text"
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search by actor, action…"
        className="w-full max-w-xs bg-brand-bg border border-brand-border focus:border-[#00C853] rounded-sm px-3 py-1.5 text-xs font-mono text-brand-text placeholder:text-brand-muted outline-none transition-colors"
      />

      {filtered.length === 0 ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
          <p className="text-xs font-mono text-brand-muted">
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
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-brand-bg transition-colors text-left"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <span className="text-[10px] font-mono text-brand-muted shrink-0">
                    {new Date(e.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="text-xs font-mono text-brand-secondary truncate">{e.action}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <span className="text-[10px] font-mono text-brand-muted">{e.actor}</span>
                  <span className="text-[10px] font-mono text-brand-muted">{expanded === e.id ? '▲' : '▼'}</span>
                </div>
              </button>
              {expanded === e.id && (
                <div className="px-4 pb-4 space-y-2 border-t border-brand-border">
                  {e.execution_id && (
                    <p className="text-[10px] font-mono text-brand-muted pt-2">execution: {e.execution_id}</p>
                  )}
                  {e.model_version && (
                    <p className="text-[10px] font-mono text-brand-muted">model: {e.model_version}</p>
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
