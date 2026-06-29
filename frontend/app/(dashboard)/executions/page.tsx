import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ExecutionsClient, type Execution } from '@/components/dashboard/executions/ExecutionsClient'

export const metadata: Metadata = { title: 'Executions' }

interface ExecutionsData {
  executions: Execution[]
  total?: number
}

export default async function ExecutionsPage() {
  let executions: Execution[] = []
  let total = 0
  try {
    const token = await getBackendToken()
    if (token) {
      const data = await apiGet<ExecutionsData>('/dashboard/executions?limit=50', token)
      executions = data.executions ?? []
      total = data.total ?? executions.length
    }
  } catch { /* backend not running */ }

  return <ExecutionsClient initialExecutions={executions} total={total} />
}
