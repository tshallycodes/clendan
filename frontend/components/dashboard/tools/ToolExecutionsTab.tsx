'use client'

import { useEffect, useState } from 'react'
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
  queued:             'text-[#4a6a4a]',
}

export function ToolExecutionsTab({ toolId }: { toolId: string }) {
  const { getToken } = useAuth()
  const [executions, setExecutions] = useState<Execution[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>('all')

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const token = await getToken()
        const params = new URLSearchParams({ tool_id: toolId, limit: '50' })
        if (filter !== 'all') params.set('status', filter)
        const res = await fetch(`${API}/v1/dashboard/executions?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          setExecutions(json.data?.executions ?? [])
          setTotal(json.data?.total ?? 0)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
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
          <div key={label} className="bg-[#111111] border border-[#1a2a1a] rounded-sm p-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a]">{label}</p>
            <p className="text-lg font-heading font-bold text-[#e8f0e8] mt-1">{value}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-1">
        {FILTERS.map(f => (
          <button key={f.key} type="button" onClick={() => setFilter(f.key)}
            className={`text-[10px] font-mono px-3 py-1.5 rounded-sm border transition-colors ${
              filter === f.key
                ? 'border-[#1a2a1a] bg-[#1a1a28] text-[#e8f0e8]'
                : 'border-transparent text-[#4a6a4a] hover:text-[#a0b8a0]'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="bg-[#111111] border border-[#1a2a1a] rounded-sm overflow-hidden">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-[#1a2a1a]">
              <th className="text-left px-4 py-2 text-[#4a6a4a] font-normal">Time</th>
              <th className="text-left px-4 py-2 text-[#4a6a4a] font-normal">Decision</th>
              <th className="text-left px-4 py-2 text-[#4a6a4a] font-normal">Status</th>
              <th className="text-right px-4 py-2 text-[#4a6a4a] font-normal">Duration</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-[#4a6a4a]">Loading…</td></tr>
            ) : executions.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-[#4a6a4a]">No executions yet</td></tr>
            ) : executions.map(e => (
              <tr key={e.id} className="border-t border-[#1a2a1a] hover:bg-[#1a1a28] transition-colors">
                <td className="px-4 py-2.5 text-[#4a6a4a]">
                  {new Date(e.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                </td>
                <td className="px-4 py-2.5 text-[#a0b8a0] max-w-[200px] truncate">{e.decision || '—'}</td>
                <td className="px-4 py-2.5">
                  <span className={STATUS_CLASS[e.status] ?? 'text-[#a0b8a0]'}>{e.status}</span>
                </td>
                <td className="px-4 py-2.5 text-right text-[#4a6a4a]">
                  {e.duration_ms != null ? `${e.duration_ms}ms` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
