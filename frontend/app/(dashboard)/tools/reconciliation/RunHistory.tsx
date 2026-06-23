'use client'

import { Select } from '@/components/ui/Select'
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

function runLabel(run: ReconciliationRun) {
  return `${fmtDate(run.period_start)} – ${fmtDate(run.period_end)} · ${run.matched_count}m ${run.unmatched_count}u ${run.flagged_count}f`
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
    <Select
      value={selectedId ?? ''}
      options={runs.map(r => ({ value: r.id, label: runLabel(r) }))}
      onChange={v => {
        const run = runs.find(r => r.id === v)
        if (run) onSelect(run)
      }}
      placeholder="Select a run to view results…"
    />
  )
}
