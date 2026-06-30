'use client'

import { useState } from 'react'
import { MagnifyingGlass } from '@phosphor-icons/react'
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
  if (!email) return 'Scheduled'
  return email.split('@')[0]
}

function runSearchText(run: ReconciliationRun): string {
  return [
    fmtDateTime(run.created_at),
    emailToName(run.triggered_by_email),
    fmtDate(run.period_start),
    fmtDate(run.period_end),
    String(run.matched_count),
    String(run.unmatched_count),
    String(run.flagged_count),
  ].join(' ').toLowerCase()
}

export function RunHistory({ runs, loading, selectedId, onSelect }: RunHistoryProps) {
  const [query, setQuery] = useState('')

  if (loading) {
    return <div className="h-9 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />
  }

  if (runs.length === 0) {
    return (
      <div className="h-9 bg-brand-surface border border-brand-border rounded-sm px-3 flex items-center">
        <span className="text-xs font-body text-brand-muted">No runs yet. Run your first reconciliation above.</span>
      </div>
    )
  }

  const filtered = query.trim()
    ? runs.filter(r => runSearchText(r).includes(query.trim().toLowerCase()))
    : runs

  return (
    <div className="space-y-2">
      <div className="relative">
        <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-muted pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search by date, period, or trigger…"
          className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm pl-8 pr-3 py-2 text-xs font-body outline-none transition-colors"
        />
      </div>
      <div className="border border-brand-border rounded-sm overflow-hidden max-h-60 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="px-3 py-3 text-xs font-body text-brand-muted">No runs match your search.</div>
        ) : (
          filtered.map((run, i) => (
            <button
              key={run.id}
              type="button"
              onClick={() => onSelect(run)}
              className={`w-full text-left px-3 py-2.5 text-xs font-body transition-colors flex items-center justify-between gap-4 ${
                i > 0 ? 'border-t border-brand-border' : ''
              } ${
                run.id === selectedId
                  ? 'bg-brand-elevated text-brand-text'
                  : 'bg-brand-surface hover:bg-brand-elevated text-brand-secondary'
              }`}
            >
              <span className="flex items-center gap-2 min-w-0">
                <span className="text-brand-muted shrink-0">{fmtDateTime(run.created_at)}</span>
                <span className="text-brand-border">·</span>
                <span className="shrink-0">{emailToName(run.triggered_by_email)}</span>
                <span className="text-brand-border">·</span>
                <span className="shrink-0">{fmtDate(run.period_start)} – {fmtDate(run.period_end)}</span>
              </span>
              <span className="flex items-center gap-2 shrink-0 text-brand-muted">
                <span>{run.matched_count} matched</span>
                <span>·</span>
                <span>{run.unmatched_count} unprocessed</span>
                {run.flagged_count > 0 && (
                  <>
                    <span>·</span>
                    <span className="text-[#ff4d6d]">{run.flagged_count} flagged</span>
                  </>
                )}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
