'use client'

import { ReconciliationRun } from './types'

interface RunHistoryProps {
  runs: ReconciliationRun[]
  loading: boolean
  selectedId: string | null
  onSelect: (run: ReconciliationRun) => void
}

function formatDateRange(start: string, end: string) {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
  return `${fmt(start)} – ${fmt(end)}`
}

function formatRunDate(ts: string) {
  return new Date(ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
}

export function RunHistory({ runs, loading, selectedId, onSelect }: RunHistoryProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />
        ))}
      </div>
    )
  }

  if (runs.length === 0) {
    return (
      <div className="bg-brand-surface border border-brand-border rounded-sm p-6 text-center">
        <p className="text-xs font-mono text-brand-muted">
          No reconciliation runs yet. Run your first reconciliation above.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {runs.map((run) => {
        const active = run.id === selectedId
        return (
          <button
            key={run.id}
            type="button"
            onClick={() => onSelect(run)}
            className="w-full text-left bg-brand-surface border border-brand-border rounded-sm px-3 py-3 hover:bg-brand-elevated transition-colors relative"
            style={active ? { borderLeft: '3px solid #00C853' } : {}}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-mono text-brand-text truncate">
                {formatDateRange(run.period_start, run.period_end)}
              </span>
              <span className="text-[10px] font-mono text-brand-muted shrink-0">
                {formatRunDate(run.created_at)}
              </span>
            </div>
            <div className="flex gap-3 mt-1">
              <span className="text-[10px] font-mono text-[#00C853]">{run.matched_count} matched</span>
              <span className="text-[10px] font-mono text-brand-secondary">{run.unmatched_count} unmatched</span>
              <span className="text-[10px] font-mono text-[#ff4d6d]">{run.flagged_count} flagged</span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
