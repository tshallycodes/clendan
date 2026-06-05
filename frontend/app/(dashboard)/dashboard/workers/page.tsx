import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import type { Worker } from '@/components/dashboard/workers/WorkerCard'
import { WorkersClient } from './WorkersClient'

export default async function WorkersPage() {
  let workers: Worker[] = []

  try {
    const token = await getBackendToken()
    if (token) {
      const res = await apiGet<{ workers: Worker[] }>('/v1/workers', token)
      workers = res.workers ?? []
    }
  } catch { /* backend not running — show empty state */ }

  return <WorkersClient initialWorkers={workers} />
}
