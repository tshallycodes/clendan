'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useToast, useCurrency } from '@/components/Providers'
import { motion, AnimatePresence } from 'framer-motion'
import { MonthPicker } from './MonthPicker'
import { CURRENCY_MAP } from '@/lib/currency'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const PAGE_SIZE = 20

const ENTRY_TYPES = [
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'accrual', label: 'Accrual' },
  { value: 'payroll', label: 'Payroll' },
  { value: 'prepayment', label: 'Prepayment' },
  { value: 'depreciation', label: 'Depreciation' },
  { value: 'manual', label: 'Manual' },
]

interface JournalLine {
  id: string
  account_code: string
  account_name: string
  debit_minor: number
  credit_minor: number
  description: string | null
}

interface JournalEntry {
  id: string
  period: string
  entry_type: string
  description: string
  status: string
  total_minor: number
  currency: string
  posted_at: string | null
  created_at: string
  lines: JournalLine[]
}

interface LineInput {
  account_code: string
  account_name: string
  debit: string
  credit: string
  description: string
}

interface Props {
  toolId: string | null
}

const STATUS_STYLE: Record<string, string> = {
  draft:            'text-brand-muted border-brand-border bg-transparent',
  pending_approval: 'text-[#00a8cc] border-[rgba(0,168,204,0.2)] bg-[rgba(0,168,204,0.08)]',
  approved:         'text-[#00C853] border-[rgba(0,200,83,0.2)] bg-[rgba(0,200,83,0.08)]',
  posted:           'text-[#00C853] border-[rgba(0,200,83,0.2)] bg-[rgba(0,200,83,0.08)]',
  voided:           'text-[#ff4d6d] border-[rgba(255,77,109,0.2)] bg-[rgba(255,77,109,0.08)]',
  rejected:         'text-[#ff4d6d] border-[rgba(255,77,109,0.2)] bg-[rgba(255,77,109,0.08)]',
}

const STATUS_LABEL: Record<string, string> = {
  draft:            'Draft',
  pending_approval: 'Pending Approval',
  approved:         'Approved',
  posted:           'Posted ✓',
  voided:           'Voided',
  rejected:         'Rejected',
}

function fmt(minor: number, currency: string): string {
  const info = CURRENCY_MAP[currency]
  const decimals = info?.decimals ?? 2
  const divisor = Math.pow(10, decimals)
  return (minor / divisor).toLocaleString('en-GB', { style: 'currency', currency: currency || 'USD' })
}

function toMinor(val: string, decimals = 2): number {
  const parsed = parseFloat(val.replace(/[^0-9.]/g, ''))
  if (isNaN(parsed)) return 0
  return Math.round(parsed * Math.pow(10, decimals))
}

// ---------------------------------------------------------------------------
// LineItemsTable
// ---------------------------------------------------------------------------

function LineItemsTable({ lines, currency }: { lines: JournalLine[]; currency: string }) {
  return (
    <table className="w-full mt-3">
      <thead>
        <tr className="border-b border-brand-border">
          {['Code', 'Account', 'Debit', 'Credit'].map((h) => (
            <th key={h} className="text-left text-[11px] font-body text-brand-muted uppercase tracking-widest px-3 py-2">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {lines.map((ln) => (
          <tr key={ln.id} className="border-b border-brand-border last:border-0">
            <td className="text-[12px] font-body text-brand-muted px-3 py-2">{ln.account_code}</td>
            <td className="text-[12px] font-body text-brand-text px-3 py-2">{ln.account_name}</td>
            <td className="text-[12px] font-body text-brand-text px-3 py-2">
              {ln.debit_minor > 0 ? fmt(ln.debit_minor, currency) : '—'}
            </td>
            <td className="text-[12px] font-body text-brand-text px-3 py-2">
              {ln.credit_minor > 0 ? fmt(ln.credit_minor, currency) : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ---------------------------------------------------------------------------
// JournalEntryCard
// ---------------------------------------------------------------------------

function JournalEntryCard({
  entry,
  onPost,
  onVoid,
  posting,
  voiding,
}: {
  entry: JournalEntry
  onPost: (id: string) => void
  onVoid: (id: string) => void
  posting: boolean
  voiding: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const statusClass = STATUS_STYLE[entry.status] ?? STATUS_STYLE.draft
  const statusLabel = STATUS_LABEL[entry.status] ?? entry.status

  return (
    <motion.div
      layout
      className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden"
    >
      <button
        type="button"
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-brand-elevated transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[11px] font-body text-brand-muted uppercase tracking-wider shrink-0">
            {entry.period}
          </span>
          <span className="text-[11px] font-body text-brand-muted shrink-0 capitalize">
            {entry.entry_type}
          </span>
          <span className="text-xs font-body text-brand-text truncate">{entry.description}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <span className="text-xs font-body text-brand-text">{fmt(entry.total_minor, entry.currency)}</span>
          <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${statusClass}`}>
            {statusLabel}
          </span>
          <span className="text-brand-muted text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            key="details"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-brand-border"
          >
            <div className="px-4 pb-3">
              <LineItemsTable lines={entry.lines} currency={entry.currency} />
              <div className="flex items-center gap-2 mt-3">
                {entry.status === 'approved' && (
                  <button
                    type="button"
                    onClick={() => onPost(entry.id)}
                    disabled={posting}
                    className="text-[12px] font-body bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 transition-all disabled:opacity-50"
                  >
                    {posting ? 'Posting…' : 'Post Entry'}
                  </button>
                )}
                {entry.status === 'draft' && (
                  <button
                    type="button"
                    onClick={() => onVoid(entry.id)}
                    disabled={voiding}
                    className="text-[12px] font-body bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] rounded-sm px-3 py-1.5 transition-colors disabled:opacity-50"
                  >
                    {voiding ? 'Voiding…' : 'Void'}
                  </button>
                )}
                {entry.posted_at && (
                  <span className="text-[11px] font-body text-brand-muted">
                    Posted {new Date(entry.posted_at).toLocaleDateString('en-GB')}
                  </span>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// JournalEntriesTab
// ---------------------------------------------------------------------------

const EMPTY_LINE = (): LineInput => ({
  account_code: '',
  account_name: '',
  debit: '',
  credit: '',
  description: '',
})

const listVariants = {
  show: { transition: { staggerChildren: 0.05 } },
}
const itemVariants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2 } },
}

export function JournalEntriesTab({ toolId }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const { currency } = useCurrency()

  const currencySymbol = CURRENCY_MAP[currency]?.symbol ?? currency
  const currencyDecimals = CURRENCY_MAP[currency]?.decimals ?? 2

  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [skip, setSkip] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  const [filterPeriod, setFilterPeriod] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [period, setPeriod] = useState('')
  const [description, setDescription] = useState('')
  const [entryType, setEntryType] = useState('adjustment')
  const [lineInputs, setLineInputs] = useState<LineInput[]>([EMPTY_LINE(), EMPTY_LINE()])
  const [submitting, setSubmitting] = useState(false)
  const [postingId, setPostingId] = useState<string | null>(null)
  const [voidingId, setVoidingId] = useState<string | null>(null)

  const totalDebits = lineInputs.reduce((s, ln) => s + toMinor(ln.debit, currencyDecimals), 0)
  const totalCredits = lineInputs.reduce((s, ln) => s + toMinor(ln.credit, currencyDecimals), 0)
  const balanced = totalDebits > 0 && totalDebits === totalCredits

  const fetchEntries = useCallback(async (currentSkip = 0, append = false) => {
    const token = await getToken()
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), skip: String(currentSkip) })
    if (filterPeriod) params.set('period', filterPeriod)

    const res = await fetch(`${API}/journal-entries?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return
    const json = await res.json()
    const fetched: JournalEntry[] = json.data?.entries ?? []
    setTotal(json.data?.total ?? 0)
    setHasMore(json.data?.has_more ?? false)
    setEntries(prev => append ? [...prev, ...fetched] : fetched)
    setLoading(false)
  }, [getToken, filterPeriod])

  useEffect(() => {
    setLoading(true)
    setSkip(0)
    fetchEntries(0, false)
  }, [fetchEntries])

  async function loadMore() {
    const nextSkip = skip + PAGE_SIZE
    setSkip(nextSkip)
    setLoadingMore(true)
    await fetchEntries(nextSkip, true)
    setLoadingMore(false)
  }

  function updateLine(idx: number, field: keyof LineInput, value: string) {
    setLineInputs((prev) => prev.map((ln, i) => (i === idx ? { ...ln, [field]: value } : ln)))
  }

  function addLine() {
    setLineInputs((prev) => [...prev, EMPTY_LINE()])
  }

  function removeLine(idx: number) {
    if (lineInputs.length <= 2) return
    setLineInputs((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleCreate() {
    if (!balanced || submitting) return
    setSubmitting(true)
    try {
      const token = await getToken()
      const lines = lineInputs
        .filter((ln) => ln.account_code || ln.account_name)
        .map((ln) => ({
          account_code: ln.account_code,
          account_name: ln.account_name,
          debit_minor: toMinor(ln.debit, currencyDecimals),
          credit_minor: toMinor(ln.credit, currencyDecimals),
          description: ln.description || undefined,
        }))

      const res = await fetch(`${API}/journal-entries`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `journal-${Date.now()}`,
        },
        body: JSON.stringify({ period, description, lines, entry_type: entryType }),
      })
      const json = await res.json().catch(() => null)
      if (!res.ok) { toast((json as { detail?: string })?.detail ?? 'Failed to create entry', 'error'); return }
      toast('Journal entry created', 'success')
      setShowForm(false)
      setPeriod('')
      setDescription('')
      setEntryType('adjustment')
      setLineInputs([EMPTY_LINE(), EMPTY_LINE()])
      setSkip(0)
      await fetchEntries(0, false)
    } catch {
      toast('Network error — please try again', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  async function handlePost(entryId: string) {
    setPostingId(entryId)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/journal-entries/${entryId}/post`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { const j = await res.json().catch(() => null); toast((j as { detail?: string })?.detail ?? 'Failed to post entry', 'error'); return }
      toast('Entry posted', 'success')
      await fetchEntries(0, false)
    } catch {
      toast('Network error — please try again', 'error')
    } finally {
      setPostingId(null)
    }
  }

  async function handleVoid(entryId: string) {
    setVoidingId(entryId)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/journal-entries/${entryId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { const j = await res.json().catch(() => null); toast((j as { detail?: string })?.detail ?? 'Failed to void entry', 'error'); return }
      toast('Entry voided', 'success')
      await fetchEntries(0, false)
    } catch {
      toast('Network error — please try again', 'error')
    } finally {
      setVoidingId(null)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest shrink-0">
            Journal Entries
          </p>
          <MonthPicker value={filterPeriod} onChange={(v) => setFilterPeriod(v)} />
          {filterPeriod && (
            <button
              type="button"
              onClick={() => setFilterPeriod('')}
              className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors"
            >
              Clear
            </button>
          )}
          {total > 0 && (
            <span className="text-[11px] font-body text-brand-muted">{total} total</span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setShowForm((p) => !p)}
          className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors shrink-0"
        >
          {showForm ? 'Cancel' : 'New Entry'}
        </button>
      </div>

      {/* New entry form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            key="form"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-body text-brand-muted uppercase tracking-widest">
                    Period
                  </label>
                  <MonthPicker value={period} onChange={setPeriod} />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-body text-brand-muted uppercase tracking-widest">
                    Type
                  </label>
                  <select
                    value={entryType}
                    onChange={(e) => setEntryType(e.target.value)}
                    className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text rounded-sm px-3 py-2 text-xs font-body outline-none transition-colors"
                  >
                    {ENTRY_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-body text-brand-muted uppercase tracking-widest">
                    Description
                  </label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="January 2025 Payroll"
                    className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-body outline-none transition-colors"
                  />
                </div>
              </div>

              {/* Lines table */}
              <div className="border border-brand-border rounded-sm overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-brand-border bg-brand-elevated">
                      {['Code', 'Account Name', `Debit (${currencySymbol})`, `Credit (${currencySymbol})`, ''].map((h) => (
                        <th
                          key={h}
                          className="text-left text-[11px] font-body text-brand-muted uppercase tracking-widest px-3 py-2"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {lineInputs.map((ln, idx) => (
                      <tr key={idx} className="border-b border-brand-border last:border-0">
                        <td className="px-2 py-1.5">
                          <input
                            value={ln.account_code}
                            onChange={(e) => updateLine(idx, 'account_code', e.target.value)}
                            placeholder="5000"
                            className="w-20 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-2 py-1 text-[12px] font-body outline-none"
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <input
                            value={ln.account_name}
                            onChange={(e) => updateLine(idx, 'account_name', e.target.value)}
                            placeholder="Payroll — Engineering"
                            className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-2 py-1 text-[12px] font-body outline-none"
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <input
                            value={ln.debit}
                            onChange={(e) => updateLine(idx, 'debit', e.target.value)}
                            placeholder="0.00"
                            inputMode="decimal"
                            className="w-28 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-2 py-1 text-[12px] font-body outline-none text-right"
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <input
                            value={ln.credit}
                            onChange={(e) => updateLine(idx, 'credit', e.target.value)}
                            placeholder="0.00"
                            inputMode="decimal"
                            className="w-28 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-2 py-1 text-[12px] font-body outline-none text-right"
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <button
                            type="button"
                            onClick={() => removeLine(idx)}
                            disabled={lineInputs.length <= 2}
                            className="text-brand-muted hover:text-[#ff4d6d] text-xs transition-colors disabled:opacity-30"
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totals + balance */}
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={addLine}
                  className="text-[12px] font-body text-brand-muted hover:text-brand-text border border-brand-border rounded-sm px-3 py-1.5 transition-colors"
                >
                  + Add Line
                </button>
                <div className="flex items-center gap-4 text-[12px] font-body">
                  <span className="text-brand-muted">
                    Dr {fmt(totalDebits, currency)} / Cr {fmt(totalCredits, currency)}
                  </span>
                  <span className={balanced ? 'text-[#00C853]' : 'text-[#ff4d6d]'}>
                    {balanced ? '✓ Balanced' : '✗ Unbalanced'}
                  </span>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={!balanced || !period || !description || submitting}
                  className="text-xs font-body bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-1.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {submitting ? 'Creating…' : 'Create Entry'}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Entries list */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-12 bg-brand-elevated border border-brand-border rounded-sm animate-pulse" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-5 py-12 text-center">
          <p className="text-xs font-body text-brand-muted">
            {filterPeriod ? `No journal entries for ${filterPeriod}.` : 'No journal entries yet — create one above.'}
          </p>
        </div>
      ) : (
        <>
          <motion.div variants={listVariants} initial="hidden" animate="show" className="space-y-2">
            {entries.map((entry) => (
              <motion.div key={entry.id} variants={itemVariants}>
                <JournalEntryCard
                  entry={entry}
                  onPost={handlePost}
                  onVoid={handleVoid}
                  posting={postingId === entry.id}
                  voiding={voidingId === entry.id}
                />
              </motion.div>
            ))}
          </motion.div>

          {hasMore && (
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="w-full py-2 text-[11px] font-body text-brand-muted border border-brand-border rounded-sm hover:text-brand-secondary hover:bg-brand-elevated transition-colors disabled:opacity-50"
            >
              {loadingMore ? 'Loading…' : `Load more (${total - entries.length} remaining)`}
            </button>
          )}
        </>
      )}
    </div>
  )
}
