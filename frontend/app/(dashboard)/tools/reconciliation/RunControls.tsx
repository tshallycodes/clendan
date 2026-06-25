'use client'

import { DatePicker } from '@/components/ui/DatePicker'

interface RunControlsProps {
  periodStart: string
  periodEnd: string
  toolReady: boolean
  running: boolean
  onPeriodStartChange: (v: string) => void
  onPeriodEndChange: (v: string) => void
  onRun: () => void
}

export function RunControls({
  periodStart,
  periodEnd,
  toolReady,
  running,
  onPeriodStartChange,
  onPeriodEndChange,
  onRun,
}: RunControlsProps) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
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
    </div>
  )
}
