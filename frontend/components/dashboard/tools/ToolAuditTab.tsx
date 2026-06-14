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
  reasoning_trace_json: string | null
}

export function ToolAuditTab({ toolId }: { toolId: string }) {
  const { getToken } = useAuth()
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
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

  if (entries.length === 0) {
    return (
      <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
        <p className="text-xs font-mono text-brand-muted">No audit entries</p>
      </div>
    )
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
          <p className="text-xs font-mono text-brand-muted">No entries match your search</p>
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
                <div className="px-4 pb-3 space-y-2 border-t border-brand-border">
                  {e.execution_id && (
                    <p className="text-[10px] font-mono text-brand-muted">execution: {e.execution_id}</p>
                  )}
                  {e.model_version && (
                    <p className="text-[10px] font-mono text-brand-muted">model: {e.model_version}</p>
                  )}
                  {e.reasoning_trace_json && (
                    <pre className="text-[10px] font-mono text-brand-secondary whitespace-pre-wrap bg-brand-bg border border-brand-border rounded-sm p-3 overflow-x-auto max-h-48">
                      {e.reasoning_trace_json}
                    </pre>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
