'use client'

import { useState, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useCurrency, useToast } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface InvoiceItem {
  id: string
  number: string | null
  contact_name: string | null
  issue_date: string | null
  due_date: string | null
  subtotal_cents: number | null
  tax_cents: number | null
  total_cents: number | null
  outstanding_cents: number | null
  paid_at: string | null
  status: string | null
  source: string | null
  currency: string | null
}

interface FlaggedItem extends InvoiceItem {
  flag_reason: string
}

interface InvoiceSummary {
  period_start: string
  period_end: string
  total_invoices: number
  paid_count: number
  overdue_count: number
  total_subtotal_cents: number
  total_tax_cents: number
  total_amount_cents: number
  total_outstanding_cents: number
  flagged: FlaggedItem[]
  items: InvoiceItem[]
}

function defaultPeriodStart() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10)
}
function defaultPeriodEnd() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().slice(0, 10)
}

function fmt(cents: number | null, symbol: string): string {
  if (cents == null) return `${symbol}0.00`
  return `${symbol}${(cents / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
}

const STATUS_STYLE: Record<string, string> = {
  paid:      'text-[#00C853] bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)]',
  overdue:   'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[rgba(255,77,109,0.2)]',
  draft:     'text-brand-muted bg-brand-elevated border border-brand-border',
  voided:    'text-brand-muted bg-brand-elevated border border-brand-border',
  authorised: 'text-[#00a8cc] bg-[rgba(0,168,204,0.08)] border border-[rgba(0,168,204,0.2)]',
}

function statusClass(s: string | null): string {
  return STATUS_STYLE[s?.toLowerCase() ?? ''] ?? 'text-brand-muted bg-brand-elevated border border-brand-border'
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-1">
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{label}</p>
      <p className="text-lg font-heading font-bold text-brand-text">{value}</p>
      {sub && <p className="text-[11px] font-body text-brand-muted">{sub}</p>}
    </div>
  )
}

interface Props {
  toolId: string | null
}

export function InvoiceRecSection({ toolId }: Props) {
  const { getToken } = useAuth()
  const { currency } = useCurrency()
  const { toast } = useToast()
  const symbol = CURRENCY_MAP[currency]?.symbol ?? currency

  const [periodStart, setPeriodStart] = useState(defaultPeriodStart)
  const [periodEnd, setPeriodEnd] = useState(defaultPeriodEnd)
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState<InvoiceSummary | null>(null)
  const [showFlagged, setShowFlagged] = useState(true)

  const run = useCallback(async () => {
    if (!toolId) { toast('Deploy the tool first', 'error'); return }
    setLoading(true)
    setSummary(null)
    try {
      const token = await getToken()
      const params = new URLSearchParams({ period_start: periodStart, period_end: periodEnd })
      if (source) params.set('source', source)
      const res = await fetch(`${API}/reconciliation/invoice-summary?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const json = await res.json().catch(() => null)
        toast(json?.error ?? `Failed (${res.status})`, 'error')
        return
      }
      const json = await res.json()
      setSummary(json.data)
    } catch {
      toast('Network error', 'error')
    } finally {
      setLoading(false)
    }
  }, [toolId, periodStart, periodEnd, source, getToken, toast])

  const inputClass = 'bg-brand-bg border border-brand-border focus:border-[#00C853] rounded-sm px-3 py-1.5 text-xs font-body text-brand-text outline-none transition-colors'
  const labelClass = 'text-[11px] font-body text-brand-muted uppercase tracking-widest'

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <p className={labelClass}>Period start</p>
            <input type="date" value={periodStart} onChange={e => setPeriodStart(e.target.value)} className={inputClass} />
          </div>
          <div className="space-y-1">
            <p className={labelClass}>Period end</p>
            <input type="date" value={periodEnd} onChange={e => setPeriodEnd(e.target.value)} className={inputClass} />
          </div>
          <div className="space-y-1">
            <p className={labelClass}>Source (optional)</p>
            <input
              type="text"
              value={source}
              onChange={e => setSource(e.target.value)}
              placeholder="e.g. xero"
              className={`${inputClass} w-32`}
            />
          </div>
          <button
            type="button"
            onClick={run}
            disabled={loading}
            className="bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-1.5 text-xs font-body transition-all disabled:opacity-40"
          >
            {loading ? 'Running…' : 'Run'}
          </button>
        </div>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-2 animate-pulse">
              <div className="h-3 bg-brand-elevated rounded w-2/3" />
              <div className="h-5 bg-brand-elevated rounded w-1/2" />
            </div>
          ))}
        </div>
      )}

      <AnimatePresence>
        {summary && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            {/* Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Total invoices" value={String(summary.total_invoices)} />
              <StatCard label="Total amount" value={fmt(summary.total_amount_cents, symbol)} />
              <StatCard label="Outstanding" value={fmt(summary.total_outstanding_cents, symbol)} sub={`${summary.overdue_count} overdue`} />
              <StatCard label="Tax collected" value={fmt(summary.total_tax_cents, symbol)} sub={`${summary.paid_count} paid`} />
            </div>

            {/* Flagged */}
            {summary.flagged.length > 0 && (
              <div className="bg-brand-surface border border-[rgba(255,77,109,0.3)] rounded-sm overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowFlagged(f => !f)}
                  className="w-full flex items-center justify-between px-4 py-3 border-b border-[rgba(255,77,109,0.2)] text-left"
                >
                  <p className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d]">
                    Flagged ({summary.flagged.length}) — missing tax
                  </p>
                  <span className="text-brand-muted text-xs">{showFlagged ? '↑' : '↓'}</span>
                </button>
                {showFlagged && (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-brand-border">
                          {['Number', 'Contact', 'Issue date', 'Subtotal', 'Tax', 'Total', 'Reason'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-[10px] font-body uppercase tracking-widest text-brand-muted">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border">
                        {summary.flagged.map(f => (
                          <tr key={f.id} className="hover:bg-brand-elevated transition-colors">
                            <td className="px-3 py-2 text-[11px] font-body text-brand-text">{f.number ?? '—'}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-secondary">{f.contact_name ?? '—'}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-muted">{fmtDate(f.issue_date)}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-text">{fmt(f.subtotal_cents, symbol)}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-[#ff4d6d]">{fmt(f.tax_cents, symbol)}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-text">{fmt(f.total_cents, symbol)}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-[#ff4d6d]">{f.flag_reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* All invoices */}
            <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-brand-border">
                <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">
                  All invoices · {fmtDate(summary.period_start)} – {fmtDate(summary.period_end)}
                </p>
              </div>
              {summary.items.length === 0 ? (
                <div className="px-4 py-8 text-center text-[11px] font-body text-brand-muted">
                  No invoices found for this period.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-brand-border">
                        {['Number', 'Contact', 'Issue date', 'Due date', 'Subtotal', 'Tax', 'Total', 'Outstanding', 'Status', 'Source'].map(h => (
                          <th key={h} className="px-3 py-2 text-left text-[10px] font-body uppercase tracking-widest text-brand-muted">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brand-border">
                      {summary.items.map(inv => (
                        <tr key={inv.id} className="hover:bg-brand-elevated transition-colors">
                          <td className="px-3 py-2 text-[11px] font-body text-brand-text">{inv.number ?? '—'}</td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-secondary">{inv.contact_name ?? '—'}</td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-muted">{fmtDate(inv.issue_date)}</td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-muted">{fmtDate(inv.due_date)}</td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-text">{fmt(inv.subtotal_cents, symbol)}</td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-text">{fmt(inv.tax_cents, symbol)}</td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-text font-medium">{fmt(inv.total_cents, symbol)}</td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-text">{fmt(inv.outstanding_cents, symbol)}</td>
                          <td className="px-3 py-2">
                            {inv.status && (
                              <span className={`text-[10px] font-body px-1.5 py-0.5 rounded-[2px] capitalize ${statusClass(inv.status)}`}>
                                {inv.status}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-[11px] font-body text-brand-muted capitalize">{inv.source ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!loading && !summary && (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-8 text-center">
          <p className="text-[11px] font-body text-brand-muted">Set a period and press Run to pull invoice data.</p>
        </div>
      )}
    </div>
  )
}
