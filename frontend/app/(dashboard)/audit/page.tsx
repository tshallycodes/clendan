import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { AuditClient } from '@/components/dashboard/audit/AuditClient'
import type { AuditEntry } from '@/components/dashboard/audit/AuditTable'
import { AnimatedPage, AnimatedSection } from '@/components/dashboard/AnimatedPage'

export const metadata: Metadata = { title: 'Audit Trail' }

interface AuditData { entries: AuditEntry[] }

export default async function AuditPage() {
  let data: AuditData | null = null
  try {
    const token = await getBackendToken()
    if (token) data = await apiGet<AuditData>('/dashboard/audit', token)
  } catch { /* backend not running */ }

  const entries = data?.entries ?? []

  return (
    <AnimatedPage className="p-6 space-y-6">
      <AnimatedSection>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-heading font-bold text-2xl text-brand-text">Audit Trail</h1>
            <p className="text-brand-muted text-xs font-mono mt-1">
              Immutable â€” append only. {entries.length} {entries.length === 1 ? 'entry' : 'entries'}.
            </p>
          </div>
        </div>
      </AnimatedSection>

      <AnimatedSection>
        <div className="bg-brand-surface border border-brand-border/50 rounded-sm px-4 py-2 text-xs font-mono text-brand-muted">
          â¬¡ This log is immutable. Records cannot be edited or deleted.
        </div>
      </AnimatedSection>

      <AnimatedSection>
        <AuditClient entries={entries} />
      </AnimatedSection>
    </AnimatedPage>
  )
}
