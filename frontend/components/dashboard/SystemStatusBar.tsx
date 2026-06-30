import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'

interface IntegrationStatus {
  status: 'connected' | 'error' | 'not_connected'
}

type DotColor = 'green' | 'red' | 'grey'

function dotColor(status: string): DotColor {
  if (status === 'connected') return 'green'
  if (status === 'error')     return 'red'
  return 'grey'
}

const DOT_STYLES: Record<DotColor, string> = {
  green: 'bg-brand-green',
  red:   'bg-brand-danger',
  grey:  'bg-brand-muted',
}

function StatusDot({ color }: { color: DotColor }) {
  return (
    <span className={`inline-block w-1.5 h-1.5 rounded-full ${DOT_STYLES[color]}`} />
  )
}

export async function SystemStatusBar() {
  let qbStatus: IntegrationStatus | null = null
  let plaidStatus: IntegrationStatus | null = null

  try {
    const token = await getBackendToken()
    if (token) {
      const [qb, plaid] = await Promise.allSettled([
        apiGet<IntegrationStatus>('/integrations/quickbooks/status', token),
        apiGet<IntegrationStatus>('/integrations/plaid/status', token),
      ])
      if (qb.status === 'fulfilled')    qbStatus    = qb.value
      if (plaid.status === 'fulfilled') plaidStatus = plaid.value
    }
  } catch { /* backend not running */ }

  const qbDot    = dotColor(qbStatus?.status ?? 'not_connected')
  const plaidDot = dotColor(plaidStatus?.status ?? 'not_connected')

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm px-5 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <span className="flex items-center gap-2 text-xs font-body text-brand-secondary">
          <StatusDot color={qbDot} />
          QuickBooks
        </span>
        <span className="flex items-center gap-2 text-xs font-body text-brand-secondary">
          <StatusDot color={plaidDot} />
          Plaid
        </span>
      </div>
      <span className="text-[10px] font-body text-brand-muted">Last health check: just now</span>
    </div>
  )
}
