import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { StatCard } from '@/components/dashboard/StatCard'
import { StatusBadge } from '@/components/dashboard/StatusBadge'

interface Stats {
  executions: number
  pending_approvals: number
  active_workers: number
  invoices: number
  transactions: number
}

export default async function OverviewPage() {
  let stats: Stats | null = null
  try {
    const token = await getBackendToken()
    if (token) stats = await apiGet<Stats>('/v1/dashboard/stats', token)
  } catch { /* backend not running — show zeros */ }

  const s = stats ?? { executions: 0, pending_approvals: 0, active_workers: 0, invoices: 0, transactions: 0 }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Overview</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Agent execution summary</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard value={s.executions}        label="Total Executions" />
        <StatCard value={s.pending_approvals} label="Pending Approvals" changeDirection={s.pending_approvals > 0 ? 'down' : 'neutral'} />
        <StatCard value={s.invoices}          label="Invoices Processed" />
        <StatCard value={s.transactions}      label="Transactions Synced" />
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-brand-border">
          <h2 className="font-heading font-semibold text-brand-text text-sm">Active Workers</h2>
        </div>
        <div className="divide-y divide-brand-border">
          {s.active_workers === 0 ? (
            <p className="px-5 py-8 text-xs font-mono text-brand-muted text-center">No active workers — deploy workers to begin</p>
          ) : (
            <div className="px-5 py-4 flex items-center gap-4">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-green opacity-60" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand-green" />
              </span>
              <div className="flex-1 text-xs font-mono text-brand-text">{s.active_workers} worker{s.active_workers !== 1 ? 's' : ''} running</div>
              <StatusBadge status="active" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
