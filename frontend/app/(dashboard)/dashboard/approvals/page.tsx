import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { formatDate, formatTime } from '@/lib/utils'
import { ApproveActions } from '@/components/dashboard/ApproveActions'

interface Approval {
  id: string
  execution_id: string
  status: string
  requested_at: string
  expires_at: string
  decision: string | null
  confidence: number | null
}

interface ApprovalsData { approvals: Approval[] }

export default async function ApprovalsPage() {
  let data: ApprovalsData | null = null
  let token: string | null = null
  try {
    token = await getBackendToken()
    if (token) data = await apiGet<ApprovalsData>('/v1/dashboard/approvals', token)
  } catch { /* backend not running */ }

  const approvals = data?.approvals ?? []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Approval Queue</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">
          {approvals.length} pending {approvals.length === 1 ? 'approval' : 'approvals'}
        </p>
      </div>

      {approvals.length === 0 ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-12 text-center">
          <p className="text-xs font-mono text-brand-muted">No pending approvals</p>
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map((a) => {
            const expires = new Date(a.expires_at)
            const now = new Date()
            const urgent = (expires.getTime() - now.getTime()) < 3600_000
            return (
              <div
                key={a.id}
                className={[
                  'bg-brand-surface border rounded-sm p-5',
                  urgent ? 'border-brand-danger border-l-[3px] border-l-brand-danger' : 'border-brand-border border-l-[3px] border-l-brand-info',
                ].join(' ')}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 space-y-1">
                    <div className="text-xs font-mono text-brand-text">
                      Execution <span className="text-brand-muted">{a.execution_id.slice(0, 12)}…</span>
                    </div>
                    <div className="text-[10px] font-mono text-brand-muted">
                      Requested {formatDate(a.requested_at)} · Expires {formatDate(a.expires_at)} {formatTime(a.expires_at)}
                      {urgent && <span className="text-brand-danger ml-2">⚠ Expiring soon</span>}
                    </div>
                    {a.confidence != null && (
                      <div className="text-[10px] font-mono text-brand-secondary">
                        Confidence {(a.confidence * 100).toFixed(0)}% · Decision: {a.decision}
                      </div>
                    )}
                  </div>
                  {token && <ApproveActions approvalId={a.id} token={token} />}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
