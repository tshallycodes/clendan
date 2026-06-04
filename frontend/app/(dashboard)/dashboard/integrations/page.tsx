import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { StatusBadge } from '@/components/dashboard/StatusBadge'

interface IntegrationStatus { status: string; connected_at?: string }

export default async function IntegrationsPage() {
  let qb: IntegrationStatus | null = null
  let plaid: IntegrationStatus | null = null

  try {
    const token = await getBackendToken()
    if (token) {
      ;[qb, plaid] = await Promise.all([
        apiGet<IntegrationStatus>('/v1/integrations/quickbooks/status', token).catch(() => null),
        apiGet<IntegrationStatus>('/v1/integrations/plaid/status', token).catch(() => null),
      ])
    }
  } catch { /* backend not running */ }

  const integrations = [
    { name: 'QuickBooks', description: 'Accounting & invoicing', status: qb?.status ?? 'not_connected', connectHref: '/v1/integrations/quickbooks/connect' },
    { name: 'Plaid', description: 'Bank account & transactions', status: plaid?.status ?? 'not_connected', connectHref: null },
  ]

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Integrations</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Connect your financial systems</p>
      </div>

      <div className="space-y-3">
        {integrations.map((intg) => (
          <div key={intg.name} className={[
            'bg-brand-surface border border-brand-border rounded-sm p-5 flex items-center gap-4',
            intg.status === 'connected' ? 'border-l-[3px] border-l-brand-green' : '',
            intg.status === 'error' ? 'border-l-[3px] border-l-brand-danger' : '',
          ].join(' ')}>
            <div className="flex-1">
              <div className="text-sm font-mono text-brand-text font-medium">{intg.name}</div>
              <div className="text-xs font-mono text-brand-muted mt-0.5">{intg.description}</div>
            </div>
            <StatusBadge status={intg.status} />
          </div>
        ))}
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm p-5">
        <p className="text-xs font-mono text-brand-muted">
          To connect QuickBooks: call <code className="text-brand-warning">GET /v1/integrations/quickbooks/connect</code> with your auth token to get the OAuth URL, then redirect your user there.<br /><br />
          To connect Plaid: use the Plaid Link widget with a link token from <code className="text-brand-warning">POST /v1/integrations/plaid/link-token</code>.
        </p>
      </div>
    </div>
  )
}
