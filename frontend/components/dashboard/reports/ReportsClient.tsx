'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { AnimatedPage, AnimatedSection } from '@/components/dashboard/AnimatedPage'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ReportState {
  loading: boolean
  available: boolean
  source?: string
  reportName?: string
  raw?: unknown
  reason?: string
}

const REPORTS: { key: string; path: string; label: string }[] = [
  { key: 'pnl', path: '/reports/pnl', label: 'Profit & Loss' },
  { key: 'balance', path: '/reports/balance-sheet', label: 'Balance Sheet' },
  { key: 'vat', path: '/reports/vat', label: 'VAT' },
]

function ReportCard({ label, state }: { label: string; state: ReportState }) {
  const [open, setOpen] = useState(false)
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
      className="bg-brand-surface border border-brand-border rounded-sm p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-heading font-semibold text-sm text-brand-text">{label}</h3>
        {state.loading ? (
          <span className="h-4 w-20 bg-brand-elevated rounded-sm animate-pulse" />
        ) : state.available ? (
          <span className="text-[11px] font-body px-2 py-0.5 rounded-sm bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]">
            Live from {state.source}
          </span>
        ) : (
          <span className="text-[11px] font-body text-brand-muted">Not available</span>
        )}
      </div>

      {!state.loading && state.available && (
        <div className="mt-3">
          <button
            type="button" onClick={() => setOpen((o) => !o)}
            className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors"
          >
            {open ? 'Hide raw report' : 'View raw report'}
          </button>
          {open && (
            <pre className="mt-2 max-h-80 overflow-auto bg-brand-bg border border-brand-border rounded-sm p-3 text-[11px] font-body text-brand-secondary">
              {JSON.stringify(state.raw, null, 2)}
            </pre>
          )}
        </div>
      )}
      {!state.loading && !state.available && (
        <p className="text-[11px] font-body text-brand-muted mt-2">
          {state.reason ?? 'No report-capable accounting integration connected.'}
        </p>
      )}
    </motion.div>
  )
}

export function ReportsClient() {
  const { getToken } = useAuth()
  const [states, setStates] = useState<Record<string, ReportState>>(
    () => Object.fromEntries(REPORTS.map((r) => [r.key, { loading: true, available: false }])),
  )

  const load = useCallback(async () => {
    const token = await getToken()
    await Promise.all(REPORTS.map(async (r) => {
      try {
        const res = await fetch(`${API}${r.path}`, { headers: { Authorization: `Bearer ${token}` } })
        const j = await res.json().catch(() => ({}))
        const d = j?.data ?? {}
        setStates((s) => ({ ...s, [r.key]: {
          loading: false, available: !!d.available, source: d.source,
          reportName: d.report_name, raw: d.raw, reason: d.reason,
        } }))
      } catch {
        setStates((s) => ({ ...s, [r.key]: { loading: false, available: false, reason: 'Could not reach the reporting service.' } }))
      }
    }))
  }, [getToken])

  useEffect(() => { void load() }, [load])

  const anyAvailable = Object.values(states).some((s) => s.available)
  const allLoaded = Object.values(states).every((s) => !s.loading)

  return (
    <AnimatedPage className="p-6 space-y-6">
      <AnimatedSection>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Reports</h1>
        <p className="text-xs font-body text-brand-muted mt-1 max-w-xl leading-relaxed">
          Your books&apos; authoritative figures, pulled straight from the accounting system you operate in — not re-computed by Clendan.
        </p>
      </AnimatedSection>

      {allLoaded && !anyAvailable && (
        <AnimatedSection>
          <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-3">
            <p className="text-xs font-body text-brand-secondary">
              Connect QuickBooks or Xero on <span className="text-brand-text">Connections</span> to pull your P&amp;L, balance sheet, and VAT here.
            </p>
          </div>
        </AnimatedSection>
      )}

      <AnimatedSection>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {REPORTS.map((r) => <ReportCard key={r.key} label={r.label} state={states[r.key]} />)}
        </div>
      </AnimatedSection>
    </AnimatedPage>
  )
}
