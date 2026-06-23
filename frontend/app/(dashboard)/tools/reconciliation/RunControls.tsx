'use client'

import { Loader2 } from 'lucide-react'

interface RunControlsProps {
  periodStart: string
  periodEnd: string
  toolReady: boolean
  running: boolean
  onPeriodStartChange: (v: string) => void
  onPeriodEndChange: (v: string) => void
  onRun: () => void
}

const INPUT_CLS =
  'bg-brand-bg border border-brand-border rounded-sm text-brand-text px-3 py-2 text-xs font-mono focus:outline-none focus:border-brand-green'

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
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-wrap gap-3 items-end">
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
          Period Start
        </label>
        <input
          type="date"
          value={periodStart}
          onChange={(e) => onPeriodStartChange(e.target.value)}
          className={INPUT_CLS}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
          Period End
        </label>
        <input
          type="date"
          value={periodEnd}
          onChange={(e) => onPeriodEndChange(e.target.value)}
          className={INPUT_CLS}
        />
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
          {running && <Loader2 className="w-3 h-3 animate-spin" />}
          {running ? 'Running...' : 'Run Reconciliation'}
        </button>
      </div>
    </div>
  )
}
