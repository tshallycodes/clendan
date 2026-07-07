'use client'

import { useMemo, useState } from 'react'
import { useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { ToolPageShell, ToolResultState, type ToolRenderCtx } from '@/components/dashboard/tools/ToolPageShell'

interface PerExpense {
  expense_id: string
  amount_cents: number
  category: string | null
  account_code: string | null
  flags: string[]
  action: 'approve' | 'flag' | 'block'
  reasoning: string
}

type ActionFilter = 'all' | 'approve' | 'flag' | 'block'

const ACTION_STYLE: Record<string, string> = {
  approve: 'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
  flag:    'text-[#00a8cc] bg-[rgba(0,168,204,0.08)] border-[rgba(0,168,204,0.2)]',
  block:   'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]',
}
const ACTION_LABEL: Record<string, string> = { approve: 'Approved', flag: 'Flagged', block: 'Blocked' }

function StatCard({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-3">
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{label}</p>
      <p className={`text-lg font-heading font-bold mt-1 ${tone ?? 'text-brand-text'}`}>{value}</p>
    </div>
  )
}

function Result({ ctx }: { ctx: ToolRenderCtx }) {
  const { currency } = useCurrency()
  const sym = CURRENCY_MAP[currency]?.symbol ?? currency
  const fmt = (c: number) => `${sym}${(c / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  const [filter, setFilter] = useState<ActionFilter>('all')

  const trace = ctx.trace
  const per = useMemo(() => (trace?.per_expense as PerExpense[] | undefined) ?? [], [trace])

  const totals = useMemo(() => {
    let total = 0, approved = 0, flagged = 0, blocked = 0
    for (const e of per) {
      total += e.amount_cents
      if (e.action === 'approve') approved++
      else if (e.action === 'flag') flagged++
      else if (e.action === 'block') blocked++
    }
    return { total, approved, flagged, blocked }
  }, [per])

  if (!trace) return <ToolResultState deployed={ctx.deployed} loading={ctx.loading} notDeployedHint="Connect an accounting integration and deploy to review spend." />

  const dailyBurn = Number(trace.daily_burn_minor ?? 0)
  const projected = Number(trace.projected_month_spend_minor ?? 0)
  const highBurn = Boolean(trace.high_burn_rate)
  const burnAssessment = trace.burn_rate_assessment as string | null | undefined
  const categorySummary = trace.spend_category_summary as string | null | undefined
  const rows = filter === 'all' ? per : per.filter((e) => e.action === filter)

  const FILTERS: { key: ActionFilter; label: string }[] = [
    { key: 'all', label: `All ${per.length}` },
    { key: 'approve', label: `Approved ${totals.approved}` },
    { key: 'flag', label: `Flagged ${totals.flagged}` },
    { key: 'block', label: `Blocked ${totals.blocked}` },
  ]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Total spend" value={fmt(totals.total)} />
        <StatCard label="Expenses" value={totals.approved + totals.flagged + totals.blocked} />
        <StatCard label="Flagged" value={totals.flagged} tone={totals.flagged ? 'text-[#00a8cc]' : undefined} />
        <StatCard label="Blocked" value={totals.blocked} tone={totals.blocked ? 'text-[#ff4d6d]' : undefined} />
      </div>

      {(burnAssessment || projected > 0) && (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-2">
          <div className="flex items-center gap-2">
            <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Burn rate</p>
            {highBurn && <span className="text-[11px] font-body px-2 py-0.5 rounded-sm text-[#f5a623] bg-[rgba(245,166,35,0.08)] border border-[rgba(245,166,35,0.2)]">Elevated</span>}
          </div>
          <div className="flex gap-8 flex-wrap">
            <div><p className="text-[11px] font-body text-brand-muted">Daily burn</p><p className="text-sm font-body text-brand-text mt-0.5">{fmt(dailyBurn)}</p></div>
            <div><p className="text-[11px] font-body text-brand-muted">Projected month</p><p className="text-sm font-body text-brand-text mt-0.5">{fmt(projected)}</p></div>
          </div>
          {burnAssessment && <p className="text-xs font-body text-brand-secondary leading-relaxed">{burnAssessment}</p>}
        </div>
      )}

      {categorySummary && (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
          <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-1.5">Spend by category</p>
          <p className="text-xs font-body text-brand-secondary leading-relaxed">{categorySummary}</p>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button key={f.key} type="button" onClick={() => setFilter(f.key)}
              className={`text-[11px] font-body px-3 py-1.5 rounded-sm border transition-colors ${
                filter === f.key ? 'border-brand-border bg-brand-elevated text-brand-text' : 'border-transparent text-brand-muted hover:text-brand-secondary'
              }`}>
              {f.label}
            </button>
          ))}
        </div>

        <div className="bg-brand-surface border border-brand-border rounded-sm overflow-x-auto">
          <table className="w-full text-xs font-body min-w-[640px]">
            <thead>
              <tr className="border-b border-brand-border">
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Category</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Account</th>
                <th className="text-right px-4 py-2 text-brand-muted font-normal">Amount</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Decision</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-brand-muted">No expenses in this view.</td></tr>
              ) : rows.map((e) => (
                <tr key={e.expense_id} className="border-t border-brand-border hover:bg-brand-elevated transition-colors align-top">
                  <td className="px-4 py-2.5 text-brand-text">{e.category ?? '—'}</td>
                  <td className="px-4 py-2.5 text-brand-muted">{e.account_code ?? '—'}</td>
                  <td className="px-4 py-2.5 text-right text-brand-text tabular-nums">{fmt(e.amount_cents)}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${ACTION_STYLE[e.action]}`}>{ACTION_LABEL[e.action]}</span>
                  </td>
                  <td className="px-4 py-2.5 text-brand-secondary max-w-[320px]">
                    <p>{e.reasoning}</p>
                    {e.flags.length > 0 && <p className="text-[11px] text-[#f5a623] mt-1">{e.flags.join(' · ')}</p>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export function SpendControlClient() {
  return (
    <ToolPageShell toolSlug="spend-control" runLabel="Run spend review">
      {(ctx) => <Result ctx={ctx} />}
    </ToolPageShell>
  )
}
