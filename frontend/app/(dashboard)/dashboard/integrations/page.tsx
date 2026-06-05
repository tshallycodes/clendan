import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { IntegrationsClient } from './IntegrationsClient'

interface QbStatus { status: string; connected_at?: string }
interface PlaidStatus { status: string; connected_at?: string; accounts?: number; transactions?: number }

export default async function IntegrationsPage() {
  let qb: QbStatus | null = null
  let plaid: PlaidStatus | null = null

  try {
    const token = await getBackendToken()
    if (token) {
      ;[qb, plaid] = await Promise.all([
        apiGet<QbStatus>('/v1/integrations/quickbooks/status', token).catch(() => null),
        apiGet<PlaidStatus>('/v1/integrations/plaid/status', token).catch(() => null),
      ])
    }
  } catch { /* backend not running */ }

  return (
    <IntegrationsClient
      qbStatus={qb?.status ?? 'not_connected'}
      plaidStatus={plaid?.status ?? 'not_connected'}
      plaidAccounts={plaid?.accounts ?? 0}
      plaidTransactions={plaid?.transactions ?? 0}
    />
  )
}
