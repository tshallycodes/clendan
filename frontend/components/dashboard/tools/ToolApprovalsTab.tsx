'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Approval {
  id: string
  execution_id: string
  status: string
  requested_at: string
  expires_at: string
  decision: string | null
  confidence: number | null
  tool_type: string | null
  triggered_by: string | null
  document_filename: string | null
  document_type: string | null
  reason: string | null
  rule_triggered: string | null
}

function formatToolType(type: string | null): string {
  if (!type) return 'Agent'
  return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

function formatDocType(type: string | null): string {
  if (!type) return ''
  return type.charAt(0).toUpperCase() + type.slice(1)
}

type Filter = 'all' | 'pending' | 'approved' | 'rejected'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
]

export function ToolApprovalsTab({ toolId }: { toolId: string | null }) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(false)
  const [acting, setActing] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('pending')

  useEffect(() => {
    if (!toolId) return
    async function load() {
      setLoading(true)
      try {
        const token = await getToken()
        const res = await fetch(`${API}/dashboard/approvals?tool_id=${toolId}`, {
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

  async function respond(approvalId: string, action: 'approve' | 'reject') {
    setActing(approvalId)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/approvals/${approvalId}/respond`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      if (!res.ok) {
        toast(`Failed to ${action} — please try again`, 'error')
        return
      }
      const newStatus = action === 'approve' ? 'approved' : 'rejected'
      setApprovals(prev => prev.map(a => a.id === approvalId ? { ...a, status: newStatus } : a))
      setFilter('all')
      toast(action === 'approve' ? 'Execution approved' : 'Execution rejected', 'success')
    } catch {
      toast(`Failed to ${action} — network error`, 'error')
    } finally {
      setActing(null)
    }
  }

  const displayed = approvals.filter(a => filter === 'all' || a.status === filter)
  const pendingCount = approvals.filter(a => a.status === 'pending').length

  if (loading) {
    return <div className="py-12 text-center text-xs font-mono text-brand-muted">Loading…</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-1">
        {FILTERS.map(f => (
          <button key={f.key} type="button" onClick={() => setFilter(f.key)}
            className={cn(
              'text-[10px] font-mono px-3 py-1.5 rounded-sm border transition-colors tracking-wider uppercase',
              filter === f.key
                ? 'border-brand-green/30 bg-brand-green/10 text-brand-green'
                : 'border-brand-border bg-transparent text-brand-muted hover:text-brand-text',
            )}
          >
            {f.label}
            {f.key === 'pending' && pendingCount > 0 && (
              <span className="ml-1.5 text-[9px] bg-[rgba(0,168,204,0.15)] text-[#00a8cc] px-1 py-0.5 rounded-sm">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {displayed.length === 0 ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
          <p className="text-xs font-mono text-brand-muted">
            {filter === 'pending' ? 'No pending approvals' : `No ${filter} approvals`}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {displayed.map(a => (
            <div key={a.id} className={cn(
              'bg-brand-surface border border-brand-border border-l-[3px] rounded-sm p-4',
              a.status === 'pending' ? 'border-l-[#00a8cc]' :
              a.status === 'approved' ? 'border-l-[#00C853]' : 'border-l-[#ff4d6d]',
            )}>
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-xs font-mono font-medium text-brand-text">
                      {formatToolType(a.tool_type)}{a.document_type ? ` — ${formatDocType(a.document_type)}` : ''}
                    </p>
                    {a.confidence != null && (
                      <span className="text-[10px] font-mono text-brand-muted">{Math.round(a.confidence * 100)}% confidence</span>
                    )}
                  </div>
                  {a.document_filename && (
                    <p className="text-[11px] font-mono text-brand-secondary truncate">{a.document_filename}</p>
                  )}
                  {a.reason && (
                    <p className="text-[10px] font-mono text-brand-muted">{a.reason}</p>
                  )}
                  <p className="text-[10px] font-mono text-brand-muted">
                    Requested {new Date(a.requested_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    {' · '}Expires {new Date(a.expires_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    {a.triggered_by ? ` · by ${a.triggered_by}` : ''}
                  </p>
                </div>
                {a.status === 'pending' ? (
                  <div className="flex gap-2 shrink-0">
                    <button
                      type="button"
                      disabled={acting === a.id}
                      onClick={() => respond(a.id, 'approve')}
                      className="text-[10px] font-mono px-3 py-1.5 rounded-sm bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)] hover:bg-[rgba(0,200,83,0.15)] disabled:opacity-50 transition-colors"
                    >
                      {acting === a.id ? '…' : 'Approve'}
                    </button>
                    <button
                      type="button"
                      disabled={acting === a.id}
                      onClick={() => respond(a.id, 'reject')}
                      className="text-[10px] font-mono px-3 py-1.5 rounded-sm bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)] hover:bg-[rgba(255,77,109,0.15)] disabled:opacity-50 transition-colors"
                    >
                      {acting === a.id ? '…' : 'Reject'}
                    </button>
                  </div>
                ) : (
                  <span className={cn(
                    'text-[10px] font-mono px-2 py-0.5 rounded-sm border shrink-0',
                    a.status === 'approved'
                      ? 'text-[#00C853] border-[rgba(0,200,83,0.2)] bg-[rgba(0,200,83,0.08)]'
                      : 'text-[#ff4d6d] border-[rgba(255,77,109,0.2)] bg-[rgba(255,77,109,0.08)]',
                  )}>
                    {a.status.charAt(0).toUpperCase() + a.status.slice(1)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
