'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Approval {
  id: string
  execution_id: string
  status: string
  requested_at: string
  expires_at: string
  decision: string | null
  confidence: number | null
}

export function ToolApprovalsTab({ toolId }: { toolId: string }) {
  const { getToken } = useAuth()
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const token = await getToken()
        const res = await fetch(`${API}/v1/dashboard/approvals?tool_id=${toolId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          setApprovals(json.data?.approvals ?? [])
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [toolId, getToken])

  async function respond(approvalId: string, verdict: 'approved' | 'rejected') {
    setActing(approvalId)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/approvals/${approvalId}/respond`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ verdict }),
      })
      setApprovals(prev => prev.filter(a => a.id !== approvalId))
    } finally {
      setActing(null)
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-xs font-mono text-brand-muted">Loading…</div>
  }

  if (approvals.length === 0) {
    return (
      <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
        <p className="text-xs font-mono text-brand-muted">No pending approvals</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {approvals.map(a => (
        <div key={a.id} className="bg-brand-surface border border-brand-border border-l-[3px] border-l-[#00a8cc] rounded-sm p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1 min-w-0">
              <p className="text-xs font-mono text-brand-text truncate">{a.decision ?? 'Approval required'}</p>
              <p className="text-[10px] font-mono text-brand-muted">
                Requested {new Date(a.requested_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                {' · '}Expires {new Date(a.expires_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
              </p>
              {a.confidence != null && (
                <p className="text-[10px] font-mono text-brand-muted">Confidence {Math.round(a.confidence * 100)}%</p>
              )}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                disabled={acting === a.id}
                onClick={() => respond(a.id, 'approved')}
                className="text-[10px] font-mono px-3 py-1.5 rounded-sm bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)] hover:bg-[rgba(0,200,83,0.15)] disabled:opacity-50 transition-colors"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={acting === a.id}
                onClick={() => respond(a.id, 'rejected')}
                className="text-[10px] font-mono px-3 py-1.5 rounded-sm bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)] hover:bg-[rgba(255,77,109,0.15)] disabled:opacity-50 transition-colors"
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
