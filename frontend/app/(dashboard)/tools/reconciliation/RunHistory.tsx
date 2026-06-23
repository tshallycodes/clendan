'use client'

import { ReconciliationRun } from './types'

interface RunHistoryProps {
  runs: ReconciliationRun[]
  loading: boolean
  selectedId: string | null
  onSelect: (run: ReconciliationRun) => void
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
}

export function RunHistory({ runs, loading, selectedId, onSelect }: RunHistoryProps) {
  if (loading) {
    return <div className="h-9 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />
  }

  if (runs.length === 0) {
    return (
      <div className="h-9 bg-brand-surface border border-brand-border rounded-sm px-3 flex items-center">
        <span className="text-xs font-mono text-brand-muted">No runs yet. Run your first reconciliation above.</span>
      </div>
    )
  }

  return (
    <select
      value={selectedId ?? ''}
      onChange={e => {
        const run = runs.find(r => r.id === e.target.value)
        if (run) onSelect(run)
      }}
      className="w-full bg-brand-bg border border-brand-border text-brand-text text-xs font-mono rounded-sm px-3 py-2 focus:border-[#00C853] focus:outline-none cursor-pointer"
    >
      {!selectedId && <option value="" disabled>Select a run…</option>}
      {runs.map(run => (
        <option key={run.id} value={run.id}>
          {fmtDate(run.period_start)} – {fmtDate(run.period_end)} · {run.matched_count}m {run.unmatched_count}u {run.flagged_count}f
        </option>
      ))}
    </select>
  )
}
