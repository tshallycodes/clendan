import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ApprovalsClient, type Approval } from '@/components/dashboard/approvals/ApprovalsClient'

export const metadata: Metadata = { title: 'Approvals' }

interface ApprovalsData { approvals: Approval[] }

export default async function ApprovalsPage() {
  let approvals: Approval[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const data = await apiGet<ApprovalsData>('/dashboard/approvals?limit=100', token)
      approvals = data.approvals ?? []
    }
  } catch { /* backend not running */ }

  return <ApprovalsClient initialApprovals={approvals} />
}
