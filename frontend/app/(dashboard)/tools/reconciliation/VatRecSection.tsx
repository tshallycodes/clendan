'use client'

import { useState, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useCurrency, useToast } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface InvoiceLine {
  id: string
  number: string | null
  contact_name: string | null
  issue_date: string | null
  subtotal_cents: number | null
  tax_cents: number | null
  total_cents: number | null
  status: string | null
  source: string | null
  currency: string | null
}

interface FlaggedLine extends InvoiceLine {
  flag_reason: string
}

interface VatSummary {
  period_start: string
  period_end: string
  output_vat_cents: number
  net_sales_cents: number
  vat_position_cents: number
  total_invoices: number
  flagged_count: number
  flagged: FlaggedLine[]
  invoice_lines: InvoiceLine[]
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

function StatCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-1">
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{label}</p>
      <p className={`text-lg font-heading font-bold ${accent ? 'text-[#00C853]' : 'text-brand-text'}`}>{value}</p>
      {sub && <p className="text-[11px] font-body text-brand-muted">{sub}</p>}
    </div>
  )
}

interface Props {
  toolId: string | null
}

export function VatRecSection({ toolId }: Props) {
  const { getToken } = useAuth()
  const { currency } = useCurrency()
  const { toast } = useToast()
  const symbol = CURRENCY_MAP[currency]?.symbol ?? currency

  const [periodStart, setPeriodStart] = useState(defaultPeriodStart)
  const [periodEnd, setPeriodEnd] = useState(defaultPeriodEnd)
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState<VatSummary | null>(null)
  const [showFlagged, setShowFlagged] = useState(true)
  const [showLines, setShowLines] = useState(false)

  const run = useCallback(async () => {
    if (!toolId) { toast('Deploy the tool first', 'error'); return }
    setLoading(true)
    setSummary(null)
    try {
      const token = await getToken()
      const params = new URLSearchParams({ period_start: periodStart, period_end: periodEnd })
      if (source) params.set('source', source)
      if (toolId) params.set('tool_id', toolId)
      const res = await fetch(`${API}/reconciliation/vat-summary?${params}`, {
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
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
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
            {/* VAT position cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <StatCard label="Output VAT" value={fmt(summary.output_vat_cents, symbol)} sub="From sales invoices" />
              <StatCard label="Net sales" value={fmt(summary.net_sales_cents, symbol)} sub={`${summary.total_invoices} invoices`} />
              <StatCard label="VAT position" value={fmt(summary.vat_position_cents, symbol)} sub="Output VAT due" accent={summary.vat_position_cents > 0} />
            </div>

            {summary.flagged_count > 0 && (
              <div className="bg-[rgba(245,166,35,0.04)] border border-[rgba(245,166,35,0.3)] rounded-sm px-4 py-2.5">
                <p className="text-[11px] font-body text-[#f5a623]">
                  {summary.flagged_count} invoice{summary.flagged_count !== 1 ? 's' : ''} with no VAT recorded — review before filing.
                </p>
              </div>
            )}

            {/* Flagged */}
            {summary.flagged.length > 0 && (
              <div className="bg-brand-surface border border-[rgba(255,77,109,0.3)] rounded-sm overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowFlagged(f => !f)}
                  className="w-full flex items-center justify-between px-4 py-3 border-b border-[rgba(255,77,109,0.2)] text-left"
                >
                  <p className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d]">
                    Missing VAT ({summary.flagged.length})
                  </p>
                  <span className="text-brand-muted text-xs">{showFlagged ? '↑' : '↓'}</span>
                </button>
                {showFlagged && (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-brand-border">
                          {['Number', 'Contact', 'Issue date', 'Net', 'VAT', 'Total', 'Source', 'Flag'].map(h => (
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
                            <td className="px-3 py-2 text-[11px] font-body text-brand-muted capitalize">{f.source ?? '—'}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-[#ff4d6d]">{f.flag_reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* All invoice lines */}
            <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
              <button
                type="button"
                onClick={() => setShowLines(l => !l)}
                className="w-full flex items-center justify-between px-4 py-3 border-b border-brand-border text-left"
              >
                <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">
                  Invoice lines · {fmtDate(summary.period_start)} – {fmtDate(summary.period_end)} ({summary.invoice_lines.length})
                </p>
                <span className="text-brand-muted text-xs">{showLines ? '↑' : '↓'}</span>
              </button>
              {showLines && (
                summary.invoice_lines.length === 0 ? (
                  <div className="px-4 py-8 text-center text-[11px] font-body text-brand-muted">
                    No invoices found for this period.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-brand-border">
                          {['Number', 'Contact', 'Issue date', 'Net', 'VAT', 'Total', 'Status', 'Source'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-[10px] font-body uppercase tracking-widest text-brand-muted">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border">
                        {summary.invoice_lines.map(inv => (
                          <tr key={inv.id} className="hover:bg-brand-elevated transition-colors">
                            <td className="px-3 py-2 text-[11px] font-body text-brand-text">{inv.number ?? '—'}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-secondary">{inv.contact_name ?? '—'}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-muted">{fmtDate(inv.issue_date)}</td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-text">{fmt(inv.subtotal_cents, symbol)}</td>
                            <td className={`px-3 py-2 text-[11px] font-body ${(inv.tax_cents ?? 0) === 0 ? 'text-[#ff4d6d]' : 'text-brand-text'}`}>
                              {fmt(inv.tax_cents, symbol)}
                            </td>
                            <td className="px-3 py-2 text-[11px] font-body text-brand-text font-medium">{fmt(inv.total_cents, symbol)}</td>
                            <td className="px-3 py-2">
                              {inv.status && (
                                <span className="text-[10px] font-body px-1.5 py-0.5 rounded-[2px] capitalize text-brand-muted bg-brand-elevated border border-brand-border">
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
                )
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!loading && !summary && (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-8 text-center">
          <p className="text-[11px] font-body text-brand-muted">Set a period and press Run to calculate your VAT position.</p>
        </div>
      )}
    </div>
  )
}
