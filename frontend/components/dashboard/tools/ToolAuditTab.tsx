'use client'

import { useEffect, useState } from 'react'
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

  if (loading) {
    return <div className="py-12 text-center text-xs font-mono text-[#4a6a4a]">Loading…</div>
  }

  if (entries.length === 0) {
    return (
      <div className="bg-[#111111] border border-[#1a2a1a] rounded-sm p-8 text-center">
        <p className="text-xs font-mono text-[#4a6a4a]">No audit entries</p>
      </div>
    )
  }

  return (
    <div className="bg-[#111111] border border-[#1a2a1a] rounded-sm overflow-hidden">
      {entries.map((e, i) => (
        <div key={e.id} className={i > 0 ? 'border-t border-[#1a2a1a]' : ''}>
          <button
            type="button"
            onClick={() => setExpanded(expanded === e.id ? null : e.id)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#1a1a28] transition-colors text-left"
          >
            <div className="flex items-center gap-4 min-w-0">
              <span className="text-[10px] font-mono text-[#4a6a4a] shrink-0">
                {new Date(e.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
              </span>
              <span className="text-xs font-mono text-[#a0b8a0] truncate">{e.action}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0 ml-4">
              <span className="text-[10px] font-mono text-[#4a6a4a]">{e.actor}</span>
              <span className="text-[10px] font-mono text-[#4a6a4a]">{expanded === e.id ? '▲' : '▼'}</span>
            </div>
          </button>
          {expanded === e.id && (
            <div className="px-4 pb-3 space-y-2 border-t border-[#1a2a1a]">
              {e.execution_id && (
                <p className="text-[10px] font-mono text-[#4a6a4a]">execution: {e.execution_id}</p>
              )}
              {e.model_version && (
                <p className="text-[10px] font-mono text-[#4a6a4a]">model: {e.model_version}</p>
              )}
              {e.reasoning_trace_json && (
                <pre className="text-[10px] font-mono text-[#a0b8a0] whitespace-pre-wrap bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm p-3 overflow-x-auto max-h-48">
                  {e.reasoning_trace_json}
                </pre>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
