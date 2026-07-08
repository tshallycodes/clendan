import Link from 'next/link'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'

interface Execution {
  id: string
  tool_type: string
  decision: string
  status: string
  created_at: string
}

interface ExecutionsResponse {
  executions: Execution[]
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  const date = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  return `${date} ${time}`
}

function decisionLabel(decision: string): string {
  switch (decision) {
    case 'auto_approved':       return 'Auto'
    case 'approval_required':   return 'Approval Required'
    case 'blocked':             return 'Blocked'
    default:                    return decision
  }
}

type BadgeVariant = 'auto' | 'pending' | 'blocked'

function statusVariant(status: string): BadgeVariant {
  if (status === 'auto_approved')                     return 'auto'
  if (status === 'queued' || status === 'pending')    return 'pending'
  if (status === 'blocked')                           return 'blocked'
  return 'pending'
}

const BADGE: Record<BadgeVariant, { bg: string; text: string; border: string }> = {
  auto:    { bg: 'bg-[rgba(0,200,83,0.08)]',   text: 'text-brand-green',  border: 'border-[rgba(0,200,83,0.2)]' },
  pending: { bg: 'bg-[rgba(0,168,204,0.08)]',  text: 'text-brand-info',   border: 'border-[rgba(0,168,204,0.2)]' },
  blocked: { bg: 'bg-[rgba(255,77,109,0.08)]', text: 'text-brand-danger', border: 'border-[rgba(255,77,109,0.2)]' },
}

function StatusBadge({ variant, label }: { variant: BadgeVariant; label: string }) {
  const s = BADGE[variant]
  return (
    <span className={`text-[11px] font-body font-medium border px-2 py-0.5 rounded-sm tracking-wider ${s.bg} ${s.text} ${s.border}`}>
      {label}
    </span>
  )
}

export async function RecentExecutionsTable() {
  let executions: Execution[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const data = await apiGet<ExecutionsResponse>('/dashboard/executions?limit=10', token)
      executions = data?.executions ?? []
    }
  } catch { /* backend not running - show empty state */ }

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-brand-border">
        <h2 className="font-heading font-semibold text-brand-text text-sm">Recent Executions</h2>
      </div>

      {executions.length === 0 ? (
        <p className="px-5 py-8 text-xs font-body text-brand-muted text-center">
          No executions yet - deploy a tool and submit your first invoice
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-body">
            <thead>
              <tr className="border-b border-brand-border">
                <th className="px-5 py-3 text-left text-[11px] font-body text-brand-muted uppercase tracking-widest">Time</th>
                <th className="px-5 py-3 text-left text-[11px] font-body text-brand-muted uppercase tracking-widest">Tool</th>
                <th className="px-5 py-3 text-left text-[11px] font-body text-brand-muted uppercase tracking-widest">Decision</th>
                <th className="px-5 py-3 text-left text-[11px] font-body text-brand-muted uppercase tracking-widest">Status</th>
                <th className="px-5 py-3 text-right text-[11px] font-body text-brand-muted uppercase tracking-widest" />
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border">
              {executions.map((ex) => {
                const variant = statusVariant(ex.status)
                return (
                  <tr key={ex.id} className="hover:bg-brand-elevated transition-colors">
                    <td className="px-5 py-3 text-brand-muted whitespace-nowrap">{formatTimestamp(ex.created_at)}</td>
                    <td className="px-5 py-3 text-brand-text">{ex.tool_type}</td>
                    <td className="px-5 py-3 text-brand-secondary">{decisionLabel(ex.decision)}</td>
                    <td className="px-5 py-3">
                      <StatusBadge variant={variant} label={ex.status.toUpperCase()} />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Link
                        href="/executions"
                        className="text-brand-muted hover:text-brand-text transition-colors"
                        aria-label="View executions"
                      >
                        →
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
