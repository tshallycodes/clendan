import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import type { Worker } from '@/components/dashboard/tools/WorkerCard'
import { ToolsClient } from './ToolsClient'

export default async function ToolsPage() {
  let workers: Worker[] = []

  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ workers: Worker[] }>('/v1/tools', token)
      workers = res.workers ?? []
    }
  } catch { /* backend not running — show empty state */ }

  return <ToolsClient initialWorkers={workers} />
}
