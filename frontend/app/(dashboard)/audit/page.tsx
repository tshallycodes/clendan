import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { formatDate, formatTime } from '@/lib/utils'

interface AuditEntry {
  id: string
  actor: string
  action: string
  model_version: string
  created_at: string
  execution_id: string | null
}

interface AuditData { entries: AuditEntry[] }

export default async function AuditPage() {
  let data: AuditData | null = null
  try {
    const token = await getBackendToken()
    if (token) data = await apiGet<AuditData>('/v1/dashboard/audit', token)
  } catch { /* backend not running */ }

  const entries = data?.entries ?? []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Audit Trail</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Immutable — append only. {entries.length} entries.</p>
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {entries.length === 0 ? (
          <p className="px-5 py-12 text-xs font-mono text-brand-muted text-center">No audit entries yet</p>
        ) : (
          <div className="divide-y divide-brand-border">
            {entries.map((e) => (
              <div key={e.id} className="px-5 py-4 hover:bg-brand-elevated transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-0.5 flex-1 min-w-0">
                    <div className="text-xs font-mono text-brand-text truncate">{e.action}</div>
                    <div className="text-[10px] font-mono text-brand-muted">
                      {e.actor} · {e.model_version}
                    </div>
                  </div>
                  <div className="text-[10px] font-mono text-brand-muted whitespace-nowrap">
                    {formatDate(e.created_at)} {formatTime(e.created_at)}
                  </div>
                </div>
                {e.execution_id && (
                  <div className="mt-1 text-[10px] font-mono text-brand-muted">
                    execution <span className="text-brand-muted/60">{e.execution_id.slice(0, 16)}…</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
