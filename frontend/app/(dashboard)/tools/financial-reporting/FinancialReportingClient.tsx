'use client'

import { useState } from 'react'
import { useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { ToolPageShell, ToolResultState, type ToolRenderCtx } from '@/components/dashboard/tools/ToolPageShell'
import { BarChart } from '@/components/dashboard/tools/BarChart'

interface ClaudeResult {
  pl_summary?: string
  balance_sheet_summary?: string
  cash_flow_summary?: string
  anomalies?: string[]
  recommendations?: string[]
}

type Statement = 'pl' | 'balance' | 'cash'

const HEALTH_STYLE: Record<string, string> = {
  strong:     'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
  healthy:    'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
  stable:     'text-[#00a8cc] bg-[rgba(0,168,204,0.08)] border-[rgba(0,168,204,0.2)]',
  watch:      'text-[#f5a623] bg-[rgba(245,166,35,0.08)] border-[rgba(245,166,35,0.2)]',
  concerning: 'text-[#f5a623] bg-[rgba(245,166,35,0.08)] border-[rgba(245,166,35,0.2)]',
  at_risk:    'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]',
  critical:   'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]',
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{label}</p>
      <p className={`text-xl font-heading font-bold mt-1 tabular-nums ${tone ?? 'text-brand-text'}`}>{value}</p>
    </div>
  )
}

function StatementRow({ label, value, strong, tone }: { label: string; value: string; strong?: boolean; tone?: string }) {
  return (
    <div className={`flex items-center justify-between px-4 py-2.5 ${strong ? 'border-t border-brand-border' : ''}`}>
      <span className={`text-xs font-body ${strong ? 'text-brand-text font-medium' : 'text-brand-secondary'}`}>{label}</span>
      <span className={`text-xs font-body tabular-nums ${tone ?? (strong ? 'text-brand-text font-medium' : 'text-brand-secondary')}`}>{value}</span>
    </div>
  )
}

function Result({ ctx }: { ctx: ToolRenderCtx }) {
  const { currency } = useCurrency()
  const sym = CURRENCY_MAP[currency]?.symbol ?? currency
  const fmt = (c: number) => `${sym}${(c / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  const [tab, setTab] = useState<Statement>('pl')

  const t = ctx.trace
  if (!ctx.deployed) return <ToolResultState deployed={null} loading={ctx.loading} notDeployedHint="Connect accounting + banking and deploy to generate statements." />
  if (ctx.loading && !t) return <div className="h-40 bg-brand-elevated rounded-sm animate-pulse" />

  const n = (k: string) => Number(t?.[k] ?? 0)
  const claude = (t?.claude_result as ClaudeResult) ?? {}
  const health = (t?.health_status as string) ?? 'watch'
  const anomalies = [...(claude.anomalies ?? []), ...((t?.period_anomalies as string[]) ?? [])]
  const topRec = t?.top_recommendation
  const recommendations = claude.recommendations ?? (topRec ? [String(topRec)] : [])
  const periodStart = t?.period_start ? new Date(String(t?.period_start)).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : ''
  const periodEnd = t?.period_end ? new Date(String(t?.period_end)).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : ''

  const TABS: { key: Statement; label: string }[] = [
    { key: 'pl', label: 'Profit & Loss' },
    { key: 'balance', label: 'Balance Sheet' },
    { key: 'cash', label: 'Cash Flow' },
  ]

  return (
    <div className="space-y-5">
      {!t ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-3 text-center">
          <p className="text-xs font-body text-brand-muted">
            No report generated yet - pick a period and click <span className="text-brand-secondary">Generate report</span> to build your statements.
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          {periodStart && <span className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{periodStart} – {periodEnd}</span>}
          <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${HEALTH_STYLE[health] ?? HEALTH_STYLE.watch}`}>{health.replace(/_/g, ' ')}</span>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Metric label="Revenue" value={fmt(n('revenue_cents'))} />
        <Metric label="Net profit" value={fmt(n('net_profit_cents'))} tone={n('net_profit_cents') >= 0 ? 'text-[#00C853]' : 'text-[#ff4d6d]'} />
        <Metric label="Gross margin" value={`${Number(t?.gross_margin_pct ?? 0)}%`} />
        <Metric label="Cash position" value={fmt(n('total_bank_balance_cents'))} />
      </div>

      <div className="space-y-2">
        <div className="flex gap-1 border-b border-brand-border">
          {TABS.map((s) => (
            <button key={s.key} type="button" onClick={() => setTab(s.key)}
              className={`px-3 py-2 text-xs font-body -mb-px border-b-2 transition-colors ${
                tab === s.key ? 'border-[#00C853] text-brand-text' : 'border-transparent text-brand-muted hover:text-brand-secondary'
              }`}>
              {s.label}
            </button>
          ))}
        </div>

        <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
          {tab === 'pl' && (
            <BarChart bars={[
              { label: 'Revenue', value: n('revenue_cents'), display: fmt(n('revenue_cents')), tone: 'neutral' },
              { label: 'Gross profit', value: n('gross_profit_cents'), display: fmt(n('gross_profit_cents')), tone: n('gross_profit_cents') >= 0 ? 'positive' : 'negative' },
              { label: 'Net profit', value: n('net_profit_cents'), display: fmt(n('net_profit_cents')), tone: n('net_profit_cents') >= 0 ? 'positive' : 'negative' },
            ]} />
          )}
          {tab === 'balance' && (
            <BarChart bars={[
              { label: 'Assets', value: n('total_assets_cents'), display: fmt(n('total_assets_cents')), tone: 'neutral' },
              { label: 'Liabilities', value: n('total_liabilities_cents'), display: fmt(n('total_liabilities_cents')), tone: 'neutral' },
              { label: 'Net assets', value: n('net_assets_cents'), display: fmt(n('net_assets_cents')), tone: n('net_assets_cents') >= 0 ? 'positive' : 'negative' },
            ]} />
          )}
          {tab === 'cash' && (
            <BarChart bars={[
              { label: 'Inflows', value: n('cash_inflows_cents'), display: fmt(n('cash_inflows_cents')), tone: 'positive' },
              { label: 'Outflows', value: n('cash_outflows_cents'), display: fmt(n('cash_outflows_cents')), tone: 'neutral' },
              { label: 'Net cash', value: n('net_cash_cents'), display: fmt(n('net_cash_cents')), tone: n('net_cash_cents') >= 0 ? 'positive' : 'negative' },
            ]} />
          )}
        </div>

        <div className="bg-brand-surface border border-brand-border rounded-sm divide-y divide-brand-border">
          {tab === 'pl' && (
            <>
              <StatementRow label="Revenue" value={fmt(n('revenue_cents'))} />
              <StatementRow label="Cost of goods sold" value={`(${fmt(n('cogs_cents'))})`} />
              <StatementRow label="Gross profit" value={fmt(n('gross_profit_cents'))} strong />
              <StatementRow label="Operating expenses" value={`(${fmt(n('opex_cents'))})`} />
              <StatementRow label="Net profit" value={fmt(n('net_profit_cents'))} strong tone={n('net_profit_cents') >= 0 ? 'text-[#00C853]' : 'text-[#ff4d6d]'} />
              {claude.pl_summary && <div className="px-4 py-3"><p className="text-[11px] font-body text-brand-muted leading-relaxed">{claude.pl_summary}</p></div>}
            </>
          )}
          {tab === 'balance' && (
            <>
              <StatementRow label="Bank balance" value={fmt(n('total_bank_balance_cents'))} />
              <StatementRow label="Outstanding receivables (AR)" value={fmt(n('outstanding_ar_cents'))} />
              <StatementRow label="Total assets" value={fmt(n('total_assets_cents'))} strong />
              <StatementRow label="Outstanding payables (AP)" value={fmt(n('outstanding_ap_cents'))} />
              <StatementRow label="Total liabilities" value={fmt(n('total_liabilities_cents'))} strong />
              <StatementRow label="Net assets" value={fmt(n('net_assets_cents'))} strong tone={n('net_assets_cents') >= 0 ? 'text-[#00C853]' : 'text-[#ff4d6d]'} />
              {claude.balance_sheet_summary && <div className="px-4 py-3"><p className="text-[11px] font-body text-brand-muted leading-relaxed">{claude.balance_sheet_summary}</p></div>}
            </>
          )}
          {tab === 'cash' && (
            <>
              <StatementRow label="Cash inflows" value={fmt(n('cash_inflows_cents'))} tone="text-[#00C853]" />
              <StatementRow label="Cash outflows" value={`(${fmt(n('cash_outflows_cents'))})`} tone="text-[#ff4d6d]" />
              <StatementRow label="Net cash movement" value={fmt(n('net_cash_cents'))} strong tone={n('net_cash_cents') >= 0 ? 'text-[#00C853]' : 'text-[#ff4d6d]'} />
              {claude.cash_flow_summary && <div className="px-4 py-3"><p className="text-[11px] font-body text-brand-muted leading-relaxed">{claude.cash_flow_summary}</p></div>}
            </>
          )}
        </div>
      </div>

      {anomalies.length > 0 && (
        <div className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.2)] rounded-sm p-4 space-y-2">
          <p className="text-[11px] font-body uppercase tracking-widest text-[#f5a623]">Anomalies · {anomalies.length}</p>
          <ul className="space-y-1.5">
            {anomalies.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-xs font-body text-brand-secondary">
                <span className="text-[#f5a623] mt-0.5 shrink-0">!</span>{a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-2">
          <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Recommendations</p>
          <ul className="space-y-1.5">
            {recommendations.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-xs font-body text-brand-secondary">
                <span className="text-brand-muted mt-0.5 shrink-0">→</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

const PERIODS: { label: string; days: number }[] = [
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 60 days', days: 60 },
  { label: 'Last 90 days', days: 90 },
]

export function FinancialReportingClient() {
  const [days, setDays] = useState(30)
  return (
    <ToolPageShell
      toolSlug="financial-reporting"
      runLabel="Generate report"
      buildRunPayload={() => ({ lookback_days: days })}
      runControls={
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-brand-bg border border-brand-border focus:border-brand-green text-brand-text rounded-sm px-2 py-1.5 text-xs font-body outline-none"
        >
          {PERIODS.map((p) => <option key={p.days} value={p.days}>{p.label}</option>)}
        </select>
      }
    >
      {(ctx) => <Result ctx={ctx} />}
    </ToolPageShell>
  )
}
