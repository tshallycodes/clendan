import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { StatCard } from '@/components/dashboard/StatCard'
import { ExecutionChart } from '@/components/dashboard/ExecutionChart'
import { RecentExecutionsTable } from '@/components/dashboard/RecentExecutionsTable'
import { SystemStatusBar } from '@/components/dashboard/SystemStatusBar'
import { ToolsList } from '@/components/dashboard/ToolsList'
import { IntegrationsHealth } from '@/components/dashboard/IntegrationsHealth'
import { QuickActions } from '@/components/dashboard/QuickActions'
import { AnimatedPage, AnimatedSection } from '@/components/dashboard/AnimatedPage'
import { AutomationRing } from '@/components/dashboard/AutomationRing'

export const metadata: Metadata = { title: 'Dashboard' }

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
  autonomy_level: 'auto' | 'approve'
  status: 'active' | 'inactive'
  version: number
}

interface IntegrationSummary {
  name: string
  slug: string
  status: string
  last_synced_at: string | null
}

const INTEGRATION_SLUGS: { slug: string; name: string }[] = [
  { slug: 'quickbooks', name: 'QuickBooks' },
  { slug: 'xero', name: 'Xero' },
  { slug: 'plaid', name: 'Plaid' },
]

export default async function DashboardPage() {
  let token: string | null = null
  try { token = await getBackendToken() } catch { /* clerk unavailable */ }

  let stats: Stats | null = null
  let tools: DeployedTool[] = []
  let integrationStatuses: IntegrationSummary[] = []

  if (token) {
    const [statsResult, toolsResult, ...integrationResults] = await Promise.allSettled([
      apiGet<Stats>('/dashboard/stats', token),
      apiGet<{ tools: DeployedTool[] }>('/tools', token),
      ...INTEGRATION_SLUGS.map(({ slug }) =>
        fetch(`${API_BASE}/integrations/${slug}/status`, {
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
      }
    })
  }

  const s = stats ?? { executions: 0, pending_approvals: 0, active_tools: 0, invoices: 0, transactions: 0 }

  const statusMessage = (() => {
    if (s.active_tools === 0) return 'No tools deployed yet — deploy your first AI agent to begin automating.'
    if (s.pending_approvals > 0) return `${s.pending_approvals} decision${s.pending_approvals > 1 ? 's' : ''} need${s.pending_approvals === 1 ? 's' : ''} your review before agents can proceed.`
    return `All systems running — ${s.active_tools} tool${s.active_tools > 1 ? 's' : ''} active, no action required.`
  })()

  const statusColor = s.active_tools === 0
    ? 'text-brand-muted'
    : s.pending_approvals > 0
      ? 'text-[#f5a623]'
      : 'text-[#00C853]'

  return (
    <AnimatedPage className="p-6 space-y-6">
      <AnimatedSection>
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Dashboard</h1>
          <p className={`text-xs font-body mt-1 ${statusColor}`}>{statusMessage}</p>
        </div>
      </AnimatedSection>

      <AnimatedSection>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard
            value={s.executions}
            label="Total Executions"
            description="Times your AI agents have run tasks end-to-end"
            change="+0 today"
            changeDirection="neutral"
            delay={0}
          />
          <StatCard
            value={s.pending_approvals}
            label="Pending Approvals"
            description="Agent decisions waiting for your sign-off before action is taken"
            change={s.pending_approvals > 0 ? `${s.pending_approvals} awaiting review` : 'no action needed'}
            changeDirection={s.pending_approvals > 0 ? 'warning' : 'neutral'}
            delay={0.08}
          />
          <StatCard
            value={s.invoices}
            label="Invoices Processed"
            description="Documents extracted, classified, and matched by your agents"
            change="+0 today"
            changeDirection="neutral"
            delay={0.16}
          />
          <StatCard
            value={s.transactions}
            label="Transactions Synced"
            description="Bank records pulled from connected accounts via Plaid"
            change="+0 today"
            changeDirection="neutral"
            delay={0.24}
          />
        </div>
      </AnimatedSection>

      <AnimatedSection>
        <AutomationRing
          autoApproved={Math.max(0, s.executions - s.pending_approvals)}
          total={s.executions}
        />
      </AnimatedSection>

      <AnimatedSection><QuickActions /></AnimatedSection>

      <AnimatedSection><ToolsList tools={tools} /></AnimatedSection>

      <AnimatedSection><IntegrationsHealth integrations={integrationStatuses} /></AnimatedSection>

      <AnimatedSection><ExecutionChart /></AnimatedSection>

      <AnimatedSection><RecentExecutionsTable /></AnimatedSection>

      <AnimatedSection><SystemStatusBar /></AnimatedSection>
    </AnimatedPage>
  )
}
