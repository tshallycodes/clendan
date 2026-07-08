'use client'

import { useState } from 'react'
import { useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { ToolPageShell, ToolResultState, type ToolRenderCtx } from '@/components/dashboard/tools/ToolPageShell'

interface ClassifiedItem { id: string; classification: string; reason: string }
interface ClaudeAssessment {
  vat_position_assessment?: string
  missing_tax_risk?: 'low' | 'medium' | 'high'
  recommended_actions?: string[]
  classified_missing_items?: ClassifiedItem[]
}

const RISK_STYLE: Record<string, string> = {
  low:    'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
  medium: 'text-[#f5a623] bg-[rgba(245,166,35,0.08)] border-[rgba(245,166,35,0.2)]',
  high:   'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]',
}
const CLASS_STYLE: Record<string, string> = {
  missing_vat: 'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]',
  data_error:  'text-[#f5a623] bg-[rgba(245,166,35,0.08)] border-[rgba(245,166,35,0.2)]',
  exempt:      'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
  zero_rated:  'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
}

function VatCard({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{label}</p>
      <p className={`text-xl font-heading font-bold mt-1 tabular-nums ${tone ?? 'text-brand-text'}`}>{value}</p>
      {sub && <p className="text-[11px] font-body text-brand-muted mt-0.5">{sub}</p>}
    </div>
  )
}

function Result({ ctx }: { ctx: ToolRenderCtx }) {
  const { currency } = useCurrency()
  const sym = CURRENCY_MAP[currency]?.symbol ?? currency
  const fmt = (c: number) => `${sym}${(Math.abs(c) / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  const trace = ctx.trace
  if (!ctx.deployed) return <ToolResultState deployed={null} loading={ctx.loading} notDeployedHint="Connect an accounting integration and deploy to compute your VAT position." />
  if (ctx.loading && !trace) return <div className="h-40 bg-brand-elevated rounded-sm animate-pulse" />

  const output = Number(trace?.vat_collected_cents ?? 0)
  const input = Number(trace?.input_vat_cents ?? 0)
  const net = Number(trace?.net_vat_liability_minor ?? 0)
  const periodLabel = (trace?.period_label as string) ?? ''
  const thresholdBreached = Boolean(trace?.threshold_breached)
  const assessment = (trace?.claude_assessment as ClaudeAssessment) ?? {}
  const risk = assessment.missing_tax_risk ?? 'low'
  const items = assessment.classified_missing_items ?? []
  const actions = assessment.recommended_actions ?? []
  const netTone = net > 0 ? (thresholdBreached ? 'text-[#ff4d6d]' : 'text-[#f5a623]') : net < 0 ? 'text-[#00C853]' : 'text-brand-text'
  const netSub = net > 0 ? 'due to HMRC' : net < 0 ? 'reclaimable' : 'balanced'

  return (
    <div className="space-y-5">
      {!trace ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-3 text-center">
          <p className="text-xs font-body text-brand-muted">
            This agent hasn&apos;t run yet - pick a period and click <span className="text-brand-secondary">Run VAT check</span> to compute your position.
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          {periodLabel && <span className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Filing period · {periodLabel}</span>}
          <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${RISK_STYLE[risk]}`}>{risk} risk</span>
          {thresholdBreached && <span className="text-[11px] font-body px-2 py-0.5 rounded-sm border text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]">VAT alert</span>}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <VatCard label="Output VAT (collected)" value={fmt(output)} sub="on sales invoices" />
        <VatCard label="Input VAT (reclaimable)" value={fmt(input)} sub="on bills & expenses" />
        <VatCard label="Net VAT position" value={fmt(net)} sub={netSub} tone={netTone} />
      </div>

      {assessment.vat_position_assessment && (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-3">
          <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Filing risk assessment</p>
          <p className="text-xs font-body text-brand-secondary leading-relaxed">{assessment.vat_position_assessment}</p>
          {actions.length > 0 && (
            <ul className="space-y-1.5 pt-1">
              {actions.map((a, i) => (
                <li key={i} className="flex items-start gap-2 text-xs font-body text-brand-secondary">
                  <span className="text-brand-muted mt-0.5 shrink-0">→</span>{a}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">
          Missing tax codes · {items.length}
        </p>
        <div className="bg-brand-surface border border-brand-border rounded-sm overflow-x-auto">
          <table className="w-full text-xs font-body min-w-[560px]">
            <thead>
              <tr className="border-b border-brand-border">
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Record</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Classification</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Reason</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-8 text-center text-brand-muted">No missing tax codes detected.</td></tr>
              ) : items.map((it) => (
                <tr key={it.id} className="border-t border-brand-border hover:bg-brand-elevated transition-colors align-top">
                  <td className="px-4 py-2.5 text-brand-muted font-mono max-w-[160px] truncate" title={it.id}>{it.id}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${CLASS_STYLE[it.classification] ?? 'text-brand-secondary border-brand-border'}`}>
                      {it.classification.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-brand-secondary max-w-[360px]">{it.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

const PERIODS: { label: string; days: number }[] = [
  { label: 'This month', days: 30 },
  { label: 'This quarter', days: 90 },
  { label: 'This year', days: 365 },
]

export function TaxComplianceClient() {
  const [days, setDays] = useState(90)
  return (
    <ToolPageShell
      toolSlug="tax-compliance"
      runLabel="Run VAT check"
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
