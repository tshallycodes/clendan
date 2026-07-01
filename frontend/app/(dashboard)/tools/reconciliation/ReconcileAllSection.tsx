'use client'

import { useState, useCallback, useRef } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useCurrency, useToast } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { MonthPicker } from '@/components/ui/MonthPicker'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const MONTH_FULL = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December']

function currentMonthValue() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function monthToRange(ym: string): { start: string; end: string } {
  const [y, m] = ym.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  return {
    start: `${ym}-01`,
    end:   `${ym}-${String(last).padStart(2, '0')}`,
  }
}

type Status = 'idle' | 'running' | 'done' | 'error'

interface BankStats {
  matched_count: number
  unmatched_count: number
  flagged_count: number
  total_txn_count: number
}

interface InvoiceStats {
  total_invoices: number
  total_amount_cents: number
  total_outstanding_cents: number
  total_tax_cents: number
  flagged_count: number
}

interface VatStats {
  output_vat_cents: number
  net_sales_cents: number
  vat_position_cents: number
  flagged_count: number
}

function fmt(cents: number, symbol: string) {
  return `${symbol}${(cents / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function Stat({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div>
      <p className="text-[10px] font-body text-brand-muted uppercase tracking-widest">{label}</p>
      <p className={`text-sm font-heading font-bold mt-0.5 ${danger ? 'text-[#ff4d6d]' : 'text-brand-text'}`}>{value}</p>
    </div>
  )
}

function SummaryCard({
  title, accent, status, onDrillIn, children,
}: {
  title: string
  accent: string
  status: Status
  onDrillIn: () => void
  children?: React.ReactNode
}) {
  return (
    <div className={`bg-brand-surface border rounded-sm overflow-hidden ${status === 'error' ? 'border-[rgba(255,77,109,0.3)]' : 'border-brand-border'}`}>
      <div className="px-4 py-2.5 border-b border-brand-border flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ background: accent }} />
        <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{title}</p>
        {status === 'running' && (
          <span className="ml-auto text-[10px] font-body text-brand-muted animate-pulse">processing…</span>
        )}
        {status === 'error' && (
          <span className="ml-auto text-[10px] font-body text-[#ff4d6d]">failed</span>
        )}
      </div>
      <div className="px-4 py-4 min-h-[96px]">
        {status === 'idle' && (
          <p className="text-[11px] font-body text-brand-muted">Press Reconcile to run.</p>
        )}
        {status === 'running' && (
          <div className="space-y-2 animate-pulse">
            <div className="h-3 bg-brand-elevated rounded w-2/3" />
            <div className="h-3 bg-brand-elevated rounded w-1/2" />
            <div className="h-3 bg-brand-elevated rounded w-3/4" />
          </div>
        )}
        {status === 'error' && (
          <p className="text-[11px] font-body text-[#ff4d6d]">Could not complete — check integrations.</p>
        )}
        {status === 'done' && (
          <div className="space-y-3">
            {children}
            <button type="button" onClick={onDrillIn}
              className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors">
              View details →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

interface Props {
  toolId: string | null
  onSelectType: (type: string) => void
}

export function ReconcileAllSection({ toolId, onSelectType }: Props) {
  const { getToken } = useAuth()
  const { currency } = useCurrency()
  const { toast } = useToast()
  const symbol = CURRENCY_MAP[currency]?.symbol ?? currency

  const [month, setMonth] = useState(currentMonthValue)
  const [anyRunning, setAnyRunning] = useState(false)

  const [bankStatus, setBankStatus]       = useState<Status>('idle')
  const [invoiceStatus, setInvoiceStatus] = useState<Status>('idle')
  const [vatStatus, setVatStatus]         = useState<Status>('idle')
  const [bankData, setBankData]           = useState<BankStats | null>(null)
  const [invoiceData, setInvoiceData]     = useState<InvoiceStats | null>(null)
  const [vatData, setVatData]             = useState<VatStats | null>(null)
  const [closing, setClosing]             = useState(false)
  const [closedAt, setClosedAt]           = useState<string | null>(null)
  const [closedBy, setClosedBy]           = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const runAll = useCallback(async () => {
    if (anyRunning || !month) return
    if (!toolId) { toast('Deploy the tool first', 'error'); return }

    const { start, end } = monthToRange(month)

    setAnyRunning(true)
    setBankStatus('running')
    setInvoiceStatus('running')
    setVatStatus('running')
    setBankData(null)
    setInvoiceData(null)
    setVatData(null)

    const token = await getToken()
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` }

    // Invoice + VAT are synchronous — fire together
    const [invRes, vatRes] = await Promise.allSettled([
      fetch(`${API}/reconciliation/invoice-summary?period_start=${start}&period_end=${end}`, { headers }),
      fetch(`${API}/reconciliation/vat-summary?period_start=${start}&period_end=${end}`, { headers }),
    ])

    if (invRes.status === 'fulfilled' && invRes.value.ok) {
      const j = await invRes.value.json()
      const d = j.data
      setInvoiceData({
        total_invoices:         d.total_invoices,
        total_amount_cents:     d.total_amount_cents,
        total_outstanding_cents: d.total_outstanding_cents,
        total_tax_cents:        d.total_tax_cents,
        flagged_count:          d.flagged?.length ?? 0,
      })
      setInvoiceStatus('done')
    } else {
      setInvoiceStatus('error')
    }

    if (vatRes.status === 'fulfilled' && vatRes.value.ok) {
      const j = await vatRes.value.json()
      const d = j.data
      setVatData({
        output_vat_cents:  d.output_vat_cents,
        net_sales_cents:   d.net_sales_cents,
        vat_position_cents: d.vat_position_cents,
        flagged_count:     d.flagged_count ?? 0,
      })
      setVatStatus('done')
    } else {
      setVatStatus('error')
    }

    // Bank rec is async — enqueue then poll
    try {
      const bankRes = await fetch(`${API}/reconciliation/run`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_start: start, period_end: end, tool_id: toolId }),
      })

      // 409 means a run is already in flight — poll for it rather than erroring
      if (!bankRes.ok && bankRes.status !== 409) {
        setBankStatus('error')
        setAnyRunning(false)
        return
      }

      if (pollRef.current) clearInterval(pollRef.current)
      let elapsed = 0
      pollRef.current = setInterval(async () => {
        elapsed += 2000
        if (elapsed > 5 * 60 * 1000) {
          clearInterval(pollRef.current!)
          setBankStatus('error')
          setAnyRunning(false)
          return
        }
        const pt = await getToken()
        const pr = await fetch(`${API}/reconciliation/runs?limit=10`, {
          headers: { Authorization: `Bearer ${pt}` },
        })
        if (!pr.ok) return
        const pj = await pr.json()
        type Run = { period_start: string; status: string; matched_count: number; unmatched_count: number; flagged_count: number; total_txn_count: number }
        const runs: Run[] = pj.data?.runs ?? []
        const completed = runs.find(
          r => r.period_start.startsWith(start) && r.status === 'completed'
        )
        if (completed) {
          clearInterval(pollRef.current!)
          setBankData({
            matched_count:   completed.matched_count,
            unmatched_count: completed.unmatched_count,
            flagged_count:   completed.flagged_count,
            total_txn_count: completed.total_txn_count,
          })
          setBankStatus('done')
          setAnyRunning(false)
        }
      }, 2000)
    } catch {
      setBankStatus('error')
      setAnyRunning(false)
    }
  }, [anyRunning, month, toolId, getToken, toast])

  const monthLabel = month
    ? `${MONTH_FULL[parseInt(month.slice(5, 7)) - 1]} ${month.slice(0, 4)}`
    : ''

  const closePeriod = useCallback(async () => {
    if (!month || closing) return
    setClosing(true)
    try {
      const { start, end } = monthToRange(month)
      const token = await getToken()
      const res = await fetch(`${API}/reconciliation/close-period`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_start: start, period_end: end }),
      })
      if (!res.ok) { toast('Failed to close period', 'error'); return }
      const json = await res.json()
      setClosedAt(json.data.closed_at)
      setClosedBy(json.data.closed_by)
      toast(`${monthLabel} closed`, 'success')
    } catch {
      toast('Network error', 'error')
    } finally {
      setClosing(false)
    }
  }, [month, closing, monthLabel, getToken, toast])

  const allDone = bankStatus === 'done' && invoiceStatus === 'done' && vatStatus === 'done'

  return (
    <div className="space-y-4">
      {/* Single control row */}
      <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Period</p>
            <MonthPicker value={month} onChange={setMonth} />
          </div>
          <button
            type="button"
            onClick={runAll}
            disabled={anyRunning || !month}
            className="bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-5 py-1.5 text-xs font-body font-medium transition-all disabled:opacity-40"
          >
            {anyRunning ? 'Running…' : `Reconcile ${monthLabel}`}
          </button>
        </div>
        {allDone && (
          <p className="text-[11px] font-body text-[#00C853] mt-2">
            All reconciliations complete for {monthLabel}.
          </p>
        )}
      </div>

      {/* 3-column summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <SummaryCard title="Bank" accent="#00a8cc" status={bankStatus} onDrillIn={() => onSelectType('bank')}>
          {bankData && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Matched"   value={String(bankData.matched_count)} />
              <Stat label="Unmatched" value={String(bankData.unmatched_count)} danger={bankData.unmatched_count > 0} />
              <Stat label="Flagged"   value={String(bankData.flagged_count)}   danger={bankData.flagged_count > 0} />
              <Stat label="Total"     value={String(bankData.total_txn_count)} />
            </div>
          )}
        </SummaryCard>

        <SummaryCard title="Invoices" accent="#f5a623" status={invoiceStatus} onDrillIn={() => onSelectType('invoice')}>
          {invoiceData && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Invoices"    value={String(invoiceData.total_invoices)} />
              <Stat label="Flagged"     value={String(invoiceData.flagged_count)}  danger={invoiceData.flagged_count > 0} />
              <Stat label="Tax"         value={fmt(invoiceData.total_tax_cents, symbol)} />
              <Stat label="Outstanding" value={fmt(invoiceData.total_outstanding_cents, symbol)} danger={invoiceData.total_outstanding_cents > 0} />
            </div>
          )}
        </SummaryCard>

        <SummaryCard title="VAT" accent="#00C853" status={vatStatus} onDrillIn={() => onSelectType('vat')}>
          {vatData && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Output VAT" value={fmt(vatData.output_vat_cents, symbol)} />
              <Stat label="Net sales"  value={fmt(vatData.net_sales_cents, symbol)} />
              <Stat label="Position"   value={fmt(vatData.vat_position_cents, symbol)} />
              <Stat label="Flagged"    value={String(vatData.flagged_count)} danger={vatData.flagged_count > 0} />
            </div>
          )}
        </SummaryCard>
      </div>

      {/* Payroll — needs roster */}
      <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-3 flex items-center justify-between">
        <div>
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-0.5">Payroll</p>
          <p className="text-[11px] font-body text-brand-muted">Requires an employee roster — run manually from the Payroll tab.</p>
        </div>
        <button type="button" onClick={() => onSelectType('payroll')}
          className="text-[11px] font-body text-brand-muted hover:text-brand-text transition-colors shrink-0 ml-4">
          Go to Payroll →
        </button>
      </div>

      {/* Close Period */}
      {allDone && !closedAt && (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-0.5">Ready to close</p>
            <p className="text-xs font-body text-brand-text">All reconciliations passed for {monthLabel}.</p>
          </div>
          <button
            type="button"
            onClick={closePeriod}
            disabled={closing}
            className="bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-1.5 text-xs font-body font-medium transition-all disabled:opacity-40 shrink-0 ml-4"
          >
            {closing ? 'Closing…' : `Close ${monthLabel}`}
          </button>
        </div>
      )}
      {closedAt && (
        <div className="bg-[rgba(0,200,83,0.06)] border border-[rgba(0,200,83,0.2)] rounded-sm px-4 py-3 flex items-center gap-3">
          <span className="text-[#00C853] text-sm">✓</span>
          <div>
            <p className="text-xs font-body text-[#00C853]">{monthLabel} closed</p>
            <p className="text-[11px] font-body text-brand-muted">
              by {closedBy?.split('@')[0]} · {new Date(closedAt).toLocaleString('en-GB')}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
