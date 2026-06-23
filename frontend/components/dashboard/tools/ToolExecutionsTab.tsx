'use client'

import { Fragment, useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Execution {
  id: string
  tool_type: string
  decision: string
  confidence: number
  status: string
  duration_ms: number | null
  created_at: string
  input_ref: string
  error_message: string | null
}

type Filter = 'all' | 'auto' | 'approval_required' | 'blocked'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'auto', label: 'Auto' },
  { key: 'approval_required', label: 'Pending' },
  { key: 'blocked', label: 'Blocked' },
]

const STATUS_CLASS: Record<string, string> = {
  auto:               'text-[#00C853]',
  approval_required:  'text-[#00a8cc]',
  blocked:            'text-[#ff4d6d]',
  failed:             'text-[#ff4d6d]',
  running:            'text-[#f5a623]',
  queued:             'text-brand-muted',
}

function ElapsedTimer({ since }: { since: string }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const start = new Date(since).getTime()
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [since])
  const m = Math.floor(elapsed / 60)
  const s = elapsed % 60
  return <span className="text-[#f5a623]">{m > 0 ? `${m}m ` : ''}{s}s</span>
}

export function ToolExecutionsTab({ toolId }: { toolId: string | null }) {
  const { getToken } = useAuth()
  const [executions, setExecutions] = useState<Execution[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    if (!toolId) return
    let pollId: ReturnType<typeof setTimeout> | null = null

    async function load(silent = false) {
      if (!silent) setLoading(true)
      try {
        const token = await getToken()
        const params = new URLSearchParams({ tool_id: toolId!, limit: '50' })
        if (filter !== 'all') params.set('status', filter)
        const res = await fetch(`${API}/v1/dashboard/executions?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          const list: Execution[] = json.data?.executions ?? []
          setExecutions(list)
          setTotal(json.data?.total ?? 0)
          const hasActive = list.some(e => e.status === 'running' || e.status === 'queued')
          if (hasActive) pollId = setTimeout(() => load(true), 3000)
        }
      } finally {
        if (!silent) setLoading(false)
      }
    }
    load()
    return () => { if (pollId) clearTimeout(pollId) }
  }, [toolId, filter, getToken])

  const auto = executions.filter(e => e.status === 'auto').length
  const blocked = executions.filter(e => e.status === 'blocked').length
  const autoPercent = executions.length ? Math.round((auto / executions.length) * 100) : 0

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total', value: total },
          { label: 'Auto-executed', value: `${autoPercent}%` },
          { label: 'Blocked', value: blocked },
        ].map(({ label, value }) => (
          <div key={label} className="bg-brand-surface border border-brand-border rounded-sm p-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">{label}</p>
            <p className="text-lg font-heading font-bold text-brand-text mt-1">{value}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-1">
        {FILTERS.map(f => (
          <button key={f.key} type="button" onClick={() => setFilter(f.key)}
            className={`text-[10px] font-mono px-3 py-1.5 rounded-sm border transition-colors ${
              filter === f.key
                ? 'border-brand-border bg-brand-elevated text-brand-text'
                : 'border-transparent text-brand-muted hover:text-brand-secondary'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-brand-border">
              <th className="text-left px-4 py-2 text-brand-muted font-normal">Time</th>
              <th className="text-left px-4 py-2 text-brand-muted font-normal">Ref</th>
              <th className="text-left px-4 py-2 text-brand-muted font-normal">Decision</th>
              <th className="text-left px-4 py-2 text-brand-muted font-normal">Status</th>
              <th className="text-right px-4 py-2 text-brand-muted font-normal">Duration</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-brand-muted">Loading…</td></tr>
            ) : executions.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-brand-muted">No executions yet</td></tr>
            ) : executions.map(e => {
              const isExpanded = expanded === e.id
              const isExpandable = e.status === 'failed'
              return (
                <Fragment key={e.id}>
                  <tr
                    onClick={() => { if (isExpandable) setExpanded(isExpanded ? null : e.id) }}
                    className={`border-t border-brand-border transition-colors ${isExpandable ? 'cursor-pointer' : ''} hover:bg-brand-elevated`}
                  >
                    <td className="px-4 py-2.5 text-brand-muted">
                      {new Date(e.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-4 py-2.5 text-brand-muted max-w-[160px] truncate">{e.input_ref || '—'}</td>
                    <td className="px-4 py-2.5 text-brand-secondary max-w-[160px] truncate">{e.decision || '—'}</td>
                    <td className="px-4 py-2.5">
                      <span className={STATUS_CLASS[e.status] ?? 'text-brand-secondary'}>{e.status}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-brand-muted">
                      {e.duration_ms != null
                        ? `${(e.duration_ms / 1000).toFixed(1)}s`
                        : (e.status === 'running' || e.status === 'queued')
                          ? <ElapsedTimer since={e.created_at} />
                          : '—'}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="border-t border-brand-border bg-brand-elevated">
                      <td colSpan={5} className="px-4 py-3 space-y-2">
                        {e.input_ref && (
                          <p className="text-[10px] font-mono text-brand-muted">ref: {e.input_ref}</p>
                        )}
                        {e.error_message ? (
                          <pre className="text-[10px] font-mono text-[#ff4d6d] whitespace-pre-wrap bg-[rgba(255,77,109,0.06)] border border-[rgba(255,77,109,0.2)] rounded-sm p-3 overflow-x-auto max-h-48">
                            {e.error_message}
                          </pre>
                        ) : (
                          <p className="text-[10px] font-mono text-brand-muted">No error details recorded for this execution.</p>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
