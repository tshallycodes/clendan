'use client'

import { useState } from 'react'
import { ExecutionsClient, type Execution } from '@/components/dashboard/executions/ExecutionsClient'
import { AuditClient } from '@/components/dashboard/audit/AuditClient'
import type { AuditEntry } from '@/components/dashboard/audit/AuditTable'

type Tab = 'executions' | 'audit'

// Activity merges the run log and the immutable audit trail into one place. Each tab renders
// its existing view; a compact switcher sits above them.
export function ActivityClient({
  executions, total, auditEntries,
}: { executions: Execution[]; total: number; auditEntries: AuditEntry[] }) {
  const [tab, setTab] = useState<Tab>('executions')

  return (
    <div>
      <div className="px-6 pt-6">
        <div className="flex items-center gap-1 p-1 bg-brand-elevated border border-brand-border rounded-sm w-fit">
          {(['executions', 'audit'] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`text-xs font-body px-3 py-1.5 rounded-sm transition-colors ${
                tab === t ? 'bg-brand-surface text-brand-text' : 'text-brand-muted hover:text-brand-text'
              }`}
            >
              {t === 'executions' ? 'Executions' : 'Audit trail'}
            </button>
          ))}
        </div>
      </div>

      {tab === 'executions' ? (
        <ExecutionsClient initialExecutions={executions} total={total} />
      ) : (
        <div className="p-6">
          <div className="bg-brand-surface border border-brand-border/50 rounded-sm px-4 py-2 text-xs font-body text-brand-muted mb-4">
            This log is immutable — records cannot be edited or deleted.
          </div>
          <AuditClient entries={auditEntries} />
        </div>
      )}
    </div>
  )
}
