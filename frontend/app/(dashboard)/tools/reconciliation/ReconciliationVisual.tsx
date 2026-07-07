'use client'

import { motion } from 'framer-motion'
import type { ReconciliationRun } from './types'

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{label}</p>
      <p className={`text-sm font-heading font-bold mt-0.5 tabular-nums ${tone}`}>{value}</p>
    </div>
  )
}

/** Match-rate visual for a reconciliation run: an animated matched/unmatched bar + counts. */
export function ReconciliationVisual({ run }: { run: ReconciliationRun }) {
  const total = run.total_txn_count || 0
  const matched = run.matched_count || 0
  const unmatched = run.unmatched_count || 0
  const matchPct = total > 0 ? Math.round((matched / total) * 100) : 0
  const matchedW = total > 0 ? (matched / total) * 100 : 0
  const unmatchedW = total > 0 ? (unmatched / total) * 100 : 0

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-3">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Match rate</p>
          <p className={`text-2xl font-heading font-bold mt-0.5 tabular-nums ${matchPct >= 90 ? 'text-[#00C853]' : 'text-brand-text'}`}>{matchPct}%</p>
        </div>
        <p className="text-[11px] font-body text-brand-muted">{matched} of {total} transactions matched</p>
      </div>

      <div className="h-2.5 w-full rounded-full bg-brand-elevated overflow-hidden flex">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${matchedW}%` }}
          transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="h-full bg-[#00C853]"
        />
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${unmatchedW}%` }}
          transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="h-full bg-brand-border"
        />
      </div>

      <div className="grid grid-cols-4 gap-2">
        <Stat label="Matched" value={matched} tone="text-[#00C853]" />
        <Stat label="Unmatched" value={unmatched} tone="text-brand-secondary" />
        <Stat label="Flagged" value={run.flagged_count} tone={run.flagged_count ? 'text-[#ff4d6d]' : 'text-brand-muted'} />
        <Stat label="Review" value={run.review_count} tone={run.review_count ? 'text-[#00a8cc]' : 'text-brand-muted'} />
      </div>
    </div>
  )
}
