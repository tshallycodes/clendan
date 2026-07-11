import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ActivityClient } from '@/components/dashboard/activity/ActivityClient'
import type { Execution } from '@/components/dashboard/executions/ExecutionsClient'
import type { AuditEntry } from '@/components/dashboard/audit/AuditTable'

export const metadata: Metadata = { title: 'Activity' }

export default async function ActivityPage() {
  let executions: Execution[] = []
  let total = 0
  let auditEntries: AuditEntry[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const [ex, au] = await Promise.allSettled([
        apiGet<{ executions: Execution[]; total?: number }>('/dashboard/executions?limit=50', token),
        apiGet<{ entries: AuditEntry[] }>('/dashboard/audit', token),
      ])
      if (ex.status === 'fulfilled') {
        executions = ex.value.executions ?? []
        total = ex.value.total ?? executions.length
      }
      if (au.status === 'fulfilled') auditEntries = au.value.entries ?? []
    }
  } catch { /* backend not running */ }

  return <ActivityClient executions={executions} total={total} auditEntries={auditEntries} />
}
