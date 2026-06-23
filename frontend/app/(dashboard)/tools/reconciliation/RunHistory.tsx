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

function fmtDateTime(d: string) {
  return new Date(d).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function emailToName(email: string | null): string {
  if (!email) return 'system'
  return email.split('@')[0]
}

function runLabel(run: ReconciliationRun) {
  const period = `${fmtDate(run.period_start)} – ${fmtDate(run.period_end)}`
  const stats = `${run.matched_count} matched · ${run.unmatched_count} unprocessed · ${run.flagged_count} flagged`
  const by = emailToName(run.triggered_by_email)
  return `${fmtDateTime(run.created_at)} · ${by} · ${period} · ${stats}`
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
