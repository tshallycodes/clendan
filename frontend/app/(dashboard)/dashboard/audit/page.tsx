import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { AuditClient } from '@/components/dashboard/audit/AuditClient'
import type { AuditEntry } from '@/components/dashboard/audit/AuditTable'

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
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Audit Trail</h1>
          <p className="text-brand-muted text-xs font-mono mt-1">
            Immutable — append only. {entries.length} {entries.length === 1 ? 'entry' : 'entries'}.
          </p>
        </div>
      </div>

      <div className="bg-brand-surface border border-brand-border/50 rounded-sm px-4 py-2 text-xs font-mono text-brand-muted">
        ⬡ This log is immutable. Records cannot be edited or deleted.
      </div>

      <AuditClient entries={entries} />
    </div>
  )
}
