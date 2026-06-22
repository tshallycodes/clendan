'use client'

import { Loader2 } from 'lucide-react'

interface Account {
  id: string
  name: string
  subtype: string
  institution_name: string | null
}

interface RunControlsProps {
  periodStart: string
  periodEnd: string
  accountId: string
  accounts: Account[]
  toolReady: boolean
  running: boolean
  onPeriodStartChange: (v: string) => void
  onPeriodEndChange: (v: string) => void
  onAccountChange: (v: string) => void
  onRun: () => void
}

const INPUT_CLS =
  'bg-brand-bg border border-brand-border rounded-sm text-brand-text px-3 py-2 text-xs font-mono focus:outline-none focus:border-brand-green'

export function RunControls({
  periodStart,
  periodEnd,
  accountId,
  accounts,
  toolReady,
  running,
  onPeriodStartChange,
  onPeriodEndChange,
  onAccountChange,
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

      {accounts.length > 0 && (
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
            Account
          </label>
          <select
            value={accountId}
            onChange={(e) => onAccountChange(e.target.value)}
            className={INPUT_CLS}
          >
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.institution_name ? `${a.institution_name} — ` : ''}{a.name}{a.subtype ? ` (${a.subtype})` : ''}
              </option>
            ))}
          </select>
        </div>
      )}

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
