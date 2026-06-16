import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { StatCard } from '@/components/dashboard/StatCard'
import { ExecutionChart } from '@/components/dashboard/ExecutionChart'
import { RecentExecutionsTable } from '@/components/dashboard/RecentExecutionsTable'
import { SystemStatusBar } from '@/components/dashboard/SystemStatusBar'
import { ToolsList } from '@/components/dashboard/ToolsList'
import { IntegrationsHealth } from '@/components/dashboard/IntegrationsHealth'
import { QuickActions } from '@/components/dashboard/QuickActions'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Stats {
  executions: number
  pending_approvals: number
  active_tools: number
  invoices: number
  transactions: number
}

interface DeployedTool {
  id: string
  type: string
  autonomy_level: 'auto' | 'approve' | 'suggest'
  status: 'active' | 'inactive'
  version: number
}

interface IntegrationSummary {
  name: string
  slug: string
  status: string
  last_synced_at: string | null
  summary?: string
}

const INTEGRATION_SLUGS: { slug: string; name: string }[] = [
  { slug: 'quickbooks', name: 'QuickBooks' },
  { slug: 'xero', name: 'Xero' },
  { slug: 'plaid', name: 'Plaid' },
]

export default async function DashboardPage() {
  const token = await getBackendToken()

  let stats: Stats | null = null
  let tools: DeployedTool[] = []
  let integrationStatuses: IntegrationSummary[] = []

  if (token) {
    const [statsResult, toolsResult, ...integrationResults] = await Promise.allSettled([
      apiGet<Stats>('/v1/dashboard/stats', token),
      apiGet<{ tools: DeployedTool[] }>('/v1/tools', token),
      ...INTEGRATION_SLUGS.map(({ slug }) =>
        fetch(`${API_BASE}/v1/integrations/${slug}/status`, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          cache: 'no-store',
        }).then((r) => r.json()),
      ),
    ])

    if (statsResult.status === 'fulfilled') stats = statsResult.value
    if (toolsResult.status === 'fulfilled') tools = toolsResult.value?.tools ?? []

    integrationStatuses = INTEGRATION_SLUGS.map(({ slug, name }, i) => {
      const result = integrationResults[i]
      const data = result?.status === 'fulfilled' ? result.value?.data : null
      return {
        name,
        slug,
        status: data?.status ?? 'disconnected',
        last_synced_at: data?.last_synced_at ?? null,
        summary: data?.summary,
      }
    })
  }

  const s = stats ?? { executions: 0, pending_approvals: 0, active_tools: 0, invoices: 0, transactions: 0 }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Dashboard</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Agent execution summary</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          value={s.executions}
          label="Total Executions"
          change="+0 today"
          changeDirection="neutral"
        />
        <StatCard
          value={s.pending_approvals}
          label="Pending Approvals"
          change={s.pending_approvals > 0 ? `${s.pending_approvals} pending review` : '+0 today'}
          changeDirection={s.pending_approvals > 0 ? 'warning' : 'neutral'}
        />
        <StatCard
          value={s.invoices}
          label="Invoices Processed"
          change="+0 today"
          changeDirection="neutral"
        />
        <StatCard
          value={s.transactions}
          label="Transactions Synced"
          change="+0 today"
          changeDirection="neutral"
        />
      </div>

      <QuickActions />

      <ToolsList tools={tools} />

      <IntegrationsHealth integrations={integrationStatuses} />

      <ExecutionChart />

      <RecentExecutionsTable />

      <SystemStatusBar />
    </div>
  )
}
