import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ApprovalsClient, type Approval } from '@/components/dashboard/approvals/ApprovalsClient'

interface ApprovalsData { approvals: Approval[] }

export default async function ApprovalsPage() {
  let approvals: Approval[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const data = await apiGet<ApprovalsData>('/v1/dashboard/approvals?limit=100', token)
      approvals = data.approvals ?? []
    }
  } catch { /* backend not running */ }

  return <ApprovalsClient initialApprovals={approvals} />
}
