'use client'

import { DatePicker } from '@/components/ui/DatePicker'

const SOURCE_NAMES: Record<string, string> = {
  plaid: 'Plaid',
  truelayer: 'TrueLayer',
  mono: 'Mono',
  stripe: 'Stripe',
  paypal: 'PayPal',
  xero: 'Xero',
  quickbooks: 'QuickBooks',
  freshbooks: 'FreshBooks',
  sage: 'Sage',
}

interface RunControlsProps {
  periodStart: string
  periodEnd: string
  toolReady: boolean
  running: boolean
  bankSources: string[]
  accountingSources: string[]
  selectedSources: string[]
  onPeriodStartChange: (v: string) => void
  onPeriodEndChange: (v: string) => void
  onSourcesChange: (sources: string[]) => void
  onRun: () => void
}

function SourceToggle({
  source,
  selected,
  onToggle,
}: {
  source: string
  selected: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`px-2.5 py-1 text-[10px] font-mono rounded-sm border transition-colors ${
        selected
          ? 'bg-brand-elevated border-brand-border text-brand-text'
          : 'border-transparent text-brand-muted hover:text-brand-secondary'
      }`}
    >
      {selected && <span className="mr-1 text-[#00C853]">✓</span>}
      {SOURCE_NAMES[source] ?? source}
    </button>
  )
}

export function RunControls({
  periodStart,
  periodEnd,
  toolReady,
  running,
  bankSources,
  accountingSources,
  selectedSources,
  onPeriodStartChange,
  onPeriodEndChange,
  onSourcesChange,
  onRun,
}: RunControlsProps) {
  function toggle(source: string) {
    if (selectedSources.includes(source)) {
      onSourcesChange(selectedSources.filter(s => s !== source))
    } else {
      onSourcesChange([...selectedSources, source])
    }
  }

  const hasIntegrations = bankSources.length > 0 || accountingSources.length > 0

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-4">
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
            Period Start
          </label>
          <DatePicker value={periodStart} onChange={onPeriodStartChange} />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
            Period End
          </label>
          <DatePicker value={periodEnd} onChange={onPeriodEndChange} />
        </div>

        <div className="flex flex-col gap-1 justify-end">
          {!toolReady && !running && (
            <p className="text-[10px] font-mono text-brand-muted">Deploy the Reconciliation tool first</p>
          )}
          <button
            type="button"
            onClick={onRun}
            disabled={running || !toolReady}
            className="flex items-center gap-2 bg-[#00C853] text-black text-xs font-mono px-4 py-2 rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running && (
              <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40" strokeDashoffset="10" strokeLinecap="round" />
              </svg>
            )}
            {running ? 'Running...' : 'Run Reconciliation'}
          </button>
        </div>
      </div>

      {hasIntegrations && (
        <div className="border-t border-brand-border pt-3 flex flex-wrap gap-x-6 gap-y-2">
          {bankSources.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted shrink-0">Bank</span>
              <div className="flex gap-1 flex-wrap">
                {bankSources.map(s => (
                  <SourceToggle key={s} source={s} selected={selectedSources.includes(s)} onToggle={() => toggle(s)} />
                ))}
              </div>
            </div>
          )}
          {accountingSources.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted shrink-0">Accounting</span>
              <div className="flex gap-1 flex-wrap">
                {accountingSources.map(s => (
                  <SourceToggle key={s} source={s} selected={selectedSources.includes(s)} onToggle={() => toggle(s)} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
