import { notFound } from 'next/navigation'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { WorkerDetail } from '@/components/dashboard/workers/WorkerDetail'
import type { Worker } from '@/components/dashboard/workers/WorkerCard'
import type { Execution } from '@/components/dashboard/workers/WorkerDetail'

interface PageProps {
  params: { id: string }
}

export default async function WorkerDetailPage({ params }: PageProps) {
  const token = await getBackendToken()
  if (!token) notFound()

  let worker: Worker
  let executions: Execution[] = []

  try {
    worker = await apiGet<Worker>(`/v1/workers/${params.id}`, token)
  } catch {
    notFound()
  }

  try {
    const res = await apiGet<{ executions: Execution[] }>(
      `/v1/dashboard/executions?worker_id=${params.id}&limit=20`,
      token,
    )
    executions = res.executions ?? []
  } catch {
    // backend not running or no executions — proceed with empty list
  }

  return <WorkerDetail worker={worker!} executions={executions} />
}
