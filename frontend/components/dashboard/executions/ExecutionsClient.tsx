'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { StatusBadge } from '@/components/dashboard/StatusBadge'
import { cn } from '@/lib/utils'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export interface Execution {
  id: string
  worker_type: string
  decision: string
  confidence: number
  status: string
  duration_ms: number | null
  created_at: string
  input_ref?: string | null
  trace_id?: string | null
  version?: string | null
}

type StatusFilter = 'all' | 'auto' | 'pending' | 'blocked'

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'auto', label: 'Auto' },
  { key: 'pending', label: 'Pending' },
  { key: 'blocked', label: 'Blocked' },
]

function toWorkerLabel(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatTs(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) +
    ' ' +
    d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function StatsBar({ executions }: { executions: Execution[] }) {
  const total = executions.length
  const autoCount = executions.filter((e) => e.status === 'auto').length
  const autoPct = total > 0 ? Math.round((autoCount / total) * 100) : 0
  const blocked = executions.filter((e) => e.status === 'blocked').length
  const durations = executions.filter((e) => e.duration_ms != null).map((e) => e.duration_ms as number)
  const avgDuration =
    durations.length > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : null

  const stats = [
    { label: 'Total', value: String(total) },
    { label: 'Auto-executed', value: `${autoPct}%` },
    { label: 'Avg duration', value: avgDuration != null ? `${avgDuration}ms` : '—' },
    { label: 'Blocked', value: String(blocked) },
  ]

  return (
    <div className="grid grid-cols-4 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="bg-brand-surface border border-brand-border rounded-sm p-4">
          <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">{s.label}</div>
          <div className="text-lg font-heading font-bold text-brand-text">{s.value}</div>
        </div>
      ))}
    </div>
  )
}

interface DrawerProps {
  execution: Execution
  onClose: () => void
  onAction: (id: string, action: 'approve' | 'reject') => Promise<void>
  loadingState: 'approve' | 'reject' | null
}

function ExecutionDrawer({ execution, onClose, onAction, loadingState }: DrawerProps) {
  const [copied, setCopied] = useState(false)

  function copyTraceId() {
    if (!execution.trace_id) return
    navigator.clipboard.writeText(execution.trace_id).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      <div className="fixed right-0 top-0 h-screen w-96 bg-brand-surface border-l border-brand-border p-6 z-50 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <span className="text-xs font-mono text-brand-muted uppercase tracking-widest">Execution Detail</span>
          <button
            onClick={onClose}
            className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        <div className="space-y-5">
          <div>
            <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">Worker</div>
            <div className="text-sm font-mono text-brand-text">{toWorkerLabel(execution.worker_type)}</div>
            {execution.version && (
              <div className="text-[10px] font-mono text-brand-muted mt-0.5">v{execution.version}</div>
            )}
          </div>

          {execution.input_ref && (
            <div>
              <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">Input Reference</div>
              <div className="text-xs font-mono text-brand-secondary break-all">{execution.input_ref}</div>
            </div>
          )}

          <div>
            <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">Decision</div>
            <div className="text-sm font-mono text-brand-text capitalize">{execution.decision}</div>
            <div className="text-[10px] font-mono text-brand-muted mt-0.5">
              Confidence: {(execution.confidence * 100).toFixed(0)}%
            </div>
          </div>

          <div>
            <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">Status</div>
            <StatusBadge status={execution.status} />
          </div>

          <div>
            <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">Duration</div>
            <div
              className={cn(
                'text-sm font-mono',
                execution.duration_ms != null && execution.duration_ms > 5000
                  ? 'text-[#f5a623]'
                  : 'text-brand-text',
              )}
            >
              {execution.duration_ms != null ? `${execution.duration_ms}ms` : '—'}
            </div>
          </div>

          {execution.trace_id && (
            <div>
              <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">Trace ID</div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-brand-muted break-all flex-1">
                  {execution.trace_id}
                </span>
                <button
                  onClick={copyTraceId}
                  className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors shrink-0"
                >
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
          )}

          {execution.status === 'pending' && (
            <div className="pt-2 border-t border-brand-border">
              <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">Actions</div>
              <div className="flex gap-2">
                <button
                  onClick={() => onAction(execution.id, 'approve')}
                  disabled={loadingState !== null}
                  className="flex-1 text-[10px] font-mono py-2 bg-brand-green text-black font-medium hover:bg-[#00a844] active:scale-[0.97] transition-all rounded-sm disabled:opacity-40"
                >
                  {loadingState === 'approve' ? '...' : 'Approve'}
                </button>
                <button
                  onClick={() => onAction(execution.id, 'reject')}
                  disabled={loadingState !== null}
                  className="flex-1 text-[10px] font-mono py-2 border border-[#ff4d6d] text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.12)] active:scale-[0.97] transition-all rounded-sm disabled:opacity-40"
                >
                  {loadingState === 'reject' ? '...' : 'Reject'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

const PAGE_SIZE = 50

interface Props {
  initialExecutions: Execution[]
  total: number
}

export function ExecutionsClient({ initialExecutions, total }: Props) {
  const { getToken, userId } = useAuth()
  const [executions, setExecutions] = useState<Execution[]>(initialExecutions)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loadingMap, setLoadingMap] = useState<Record<string, 'approve' | 'reject' | null>>({})
  const [loadingMore, setLoadingMore] = useState(false)
  const [offset, setOffset] = useState(initialExecutions.length)

  const filtered = executions.filter((e) => {
    const matchStatus = statusFilter === 'all' || e.status === statusFilter
    const matchSearch = search === '' || e.decision.toLowerCase().includes(search.toLowerCase())
    return matchStatus && matchSearch
  })

  const selected = executions.find((e) => e.id === selectedId) ?? null

  async function handleAction(id: string, action: 'approve' | 'reject') {
    setLoadingMap((prev) => ({ ...prev, [id]: action }))
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(`${API_BASE}/v1/approvals/${id}/respond`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, responder_id: userId }),
      })
      if (res.ok) {
        setExecutions((prev) =>
          prev.map((e) =>
            e.id === id ? { ...e, status: action === 'approve' ? 'auto' : 'blocked' } : e,
          ),
        )
      }
    } finally {
      setLoadingMap((prev) => ({ ...prev, [id]: null }))
    }
  }

  async function loadMore() {
    setLoadingMore(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(
        `${API_BASE}/v1/dashboard/executions?limit=${PAGE_SIZE}&offset=${offset}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!res.ok) return
      const json = await res.json()
      const next: Execution[] = json.data?.executions ?? []
      setExecutions((prev) => [...prev, ...next])
      setOffset((prev) => prev + next.length)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Execution Log</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">{total} executions total</p>
      </div>

      <StatsBar executions={executions} />

      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setStatusFilter(f.key)}
              className={cn(
                'text-[10px] font-mono px-3 py-1.5 rounded-sm border transition-colors tracking-wider uppercase',
                statusFilter === f.key
                  ? 'border-brand-green/30 bg-brand-green/10 text-brand-green'
                  : 'border-brand-border bg-transparent text-brand-muted hover:text-brand-text',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by decision…"
          className="flex-1 max-w-xs bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-1.5 text-xs font-mono text-brand-text placeholder:text-brand-muted outline-none transition-colors"
        />
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {filtered.length === 0 ? (
          <p className="px-5 py-12 text-xs font-mono text-brand-muted text-center">
            No executions yet — deploy a worker to begin
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-brand-border">
                  {['Timestamp', 'Worker', 'Decision', 'Status', 'Duration', ''].map((h, i) => (
                    <th
                      key={i}
                      className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-5 py-3"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((e) => (
                  <tr
                    key={e.id}
                    className="border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors cursor-pointer"
                    onClick={() => setSelectedId(e.id === selectedId ? null : e.id)}
                  >
                    <td className="px-5 py-3 text-xs font-mono text-brand-muted whitespace-nowrap">
                      {formatTs(e.created_at)}
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-text whitespace-nowrap">
                      {toWorkerLabel(e.worker_type)}
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-text capitalize">
                      {e.decision}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={e.status} />
                    </td>
                    <td
                      className={cn(
                        'px-5 py-3 text-xs font-mono',
                        e.duration_ms != null && e.duration_ms > 5000
                          ? 'text-[#f5a623]'
                          : 'text-brand-muted',
                      )}
                    >
                      {e.duration_ms != null ? `${e.duration_ms}ms` : '—'}
                    </td>
                    <td className="px-5 py-3">
                      <span className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors">
                        View →
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {executions.length < total && (
        <div className="flex justify-center">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="text-[10px] font-mono px-4 py-2 border border-brand-border text-brand-muted hover:text-brand-text hover:border-brand-secondary transition-colors rounded-sm disabled:opacity-40"
          >
            {loadingMore ? 'Loading…' : 'Load more'}
          </button>
        </div>
      )}

      {selected && (
        <ExecutionDrawer
          execution={selected}
          onClose={() => setSelectedId(null)}
          onAction={handleAction}
          loadingState={loadingMap[selected.id] ?? null}
        />
      )}
    </div>
  )
}
