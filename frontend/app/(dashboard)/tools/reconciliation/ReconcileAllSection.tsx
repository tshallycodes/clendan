'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useCurrency, useToast } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { MonthPicker } from '@/components/ui/MonthPicker'
import { IntegrationLogo } from '@/app/(dashboard)/dashboard/integrations/IntegrationLogo'

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
  paid_count?: number
  overdue_count?: number
}

interface VatStats {
  output_vat_cents: number
  net_sales_cents: number
  vat_position_cents: number
  flagged_count: number
}

interface RosterEntry {
  name: string
  expected_minor: number
}

interface PayrollStats {
  matched_count: number
  ghost_count: number
  missing_count: number
  discrepancy_count: number
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
          <p className="text-[11px] font-body text-[#ff4d6d]">Could not complete - check integrations.</p>
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
  onViewAudit: (actionPrefix: string) => void
}

export function ReconcileAllSection({ toolId, onViewAudit }: Props) {
  const { getToken } = useAuth()
  const { currency } = useCurrency()
  const { toast } = useToast()
  const symbol = CURRENCY_MAP[currency]?.symbol ?? currency

  const [month, setMonth] = useState(currentMonthValue)
  const [anyRunning, setAnyRunning] = useState(false)

  const [roster, setRoster]               = useState<RosterEntry[]>([])
  const [bankStatus, setBankStatus]       = useState<Status>('idle')
  const [invoiceStatus, setInvoiceStatus] = useState<Status>('idle')
  const [vatStatus, setVatStatus]         = useState<Status>('idle')
  const [payrollStatus, setPayrollStatus] = useState<Status>('idle')
  const [bankData, setBankData]           = useState<BankStats | null>(null)
  const [invoiceData, setInvoiceData]     = useState<InvoiceStats | null>(null)
  const [vatData, setVatData]             = useState<VatStats | null>(null)
  const [payrollData, setPayrollData]     = useState<PayrollStats | null>(null)
  const [closing, setClosing]             = useState(false)
  const [reopening, setReopening]         = useState(false)
  const [closedAt, setClosedAt]           = useState<string | null>(null)
  const [closedBy, setClosedBy]           = useState<string | null>(null)
  const [bankApprovalState, setBankApprovalState] = useState<'none' | 'pending' | 'approved' | 'rejected'>('none')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const approvalPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!toolId) return
    async function loadRoster() {
      const token = await getToken()
      const h = { Authorization: `Bearer ${token}` }

      // Primary: saved_employees in tool config_json
      const toolRes = await fetch(`${API}/tools/${toolId}`, { headers: h })
      if (toolRes.ok) {
        const toolJson = await toolRes.json()
        const cfg = (toolJson.data?.config_json ?? {}) as Record<string, unknown>
        const employees = cfg.saved_employees as RosterEntry[] | undefined
        if (Array.isArray(employees) && employees.length > 0) {
          setRoster(employees)
          return
        }
      }

      // Fallback: roster_json from the most recent payroll run
      const runsRes = await fetch(`${API}/payroll-runs`, { headers: h })
      if (runsRes.ok) {
        const runsJson = await runsRes.json()
        const runs: Array<{ roster_json?: RosterEntry[] }> = runsJson.data?.runs ?? []
        const roster = runs[0]?.roster_json
        if (Array.isArray(roster) && roster.length > 0) {
          setRoster(roster)
        }
      }
    }
    loadRoster()
  }, [toolId, getToken])

  // Restore the most recent results whenever month or toolId changes
  useEffect(() => {
    setBankStatus('idle');    setBankData(null)
    setInvoiceStatus('idle'); setInvoiceData(null)
    setVatStatus('idle');     setVatData(null)
    setPayrollStatus('idle'); setPayrollData(null)
    setClosedAt(null);        setClosedBy(null)
    setBankApprovalState('none')

    if (!month || !toolId) return

    let cancelled = false
    async function loadRecentResults() {
      const token = await getToken()
      const { start, end } = monthToRange(month)
      const h = { Authorization: `Bearer ${token}` }

      const [bankRunsRes, invoiceRes, vatRes, payrollRunsRes, closeRes] = await Promise.allSettled([
        fetch(`${API}/reconciliation/runs?limit=100`, { headers: h }),
        fetch(`${API}/reconciliation/invoice-summary?period_start=${start}&period_end=${end}&tool_id=${toolId}`, { headers: h }),
        fetch(`${API}/reconciliation/vat-summary?period_start=${start}&period_end=${end}&tool_id=${toolId}`, { headers: h }),
        fetch(`${API}/payroll-runs`, { headers: h }),
        fetch(`${API}/reconciliation/close-period-status?period_start=${start}&period_end=${end}`, { headers: h }),
      ])

      if (cancelled) return

      // Bank - restore from most recent completed stored run for this period
      if (bankRunsRes.status === 'fulfilled' && bankRunsRes.value.ok) {
        const j = await bankRunsRes.value.json()
        type BankRun = { period_start: string; status: string; matched_count: number; unmatched_count: number; flagged_count: number; total_txn_count: number }
        const run: BankRun | undefined = (j.data?.runs ?? []).find(
          (r: BankRun) => r.period_start.startsWith(start) && r.status === 'completed'
        )
        if (run && !cancelled) {
          setBankData({ matched_count: run.matched_count, unmatched_count: run.unmatched_count, flagged_count: run.flagged_count, total_txn_count: run.total_txn_count })
          setBankStatus('done')
          // Check approval table directly for this period
          try {
            const token = await getToken()
            const apr = await fetch(`${API}/reconciliation/approval-status?period_start=${start}&period_end=${end}`, { headers: { Authorization: `Bearer ${token}` } })
            if (apr.ok && !cancelled) {
              const aData = (await apr.json()).data
              if (aData.approval_status === 'pending') setBankApprovalState('pending')
              else if (aData.approval_status === 'approved') setBankApprovalState('approved')
              else if (aData.approval_status === 'rejected') setBankApprovalState('rejected')
              else setBankApprovalState('none')
            }
          } catch { setBankApprovalState('none') }
        }
      }

      // Invoice - live query, always reflects current accounting data
      if (invoiceRes.status === 'fulfilled' && invoiceRes.value.ok && !cancelled) {
        const j = await invoiceRes.value.json()
        const d = j.data
        if (d) {
          setInvoiceData({ total_invoices: d.total_invoices, total_amount_cents: d.total_amount_cents, total_outstanding_cents: d.total_outstanding_cents, total_tax_cents: d.total_tax_cents, flagged_count: d.flagged?.length ?? d.flagged_count ?? 0, paid_count: d.paid_count, overdue_count: d.overdue_count })
          setInvoiceStatus('done')
        }
      }

      // VAT - live query
      if (vatRes.status === 'fulfilled' && vatRes.value.ok && !cancelled) {
        const j = await vatRes.value.json()
        const d = j.data
        if (d && !cancelled) {
          setVatData({ output_vat_cents: d.output_vat_cents, net_sales_cents: d.net_sales_cents, vat_position_cents: d.vat_position_cents, flagged_count: d.flagged_count ?? 0 })
          setVatStatus('done')
        }
      }

      // Payroll - restore from most recent completed run for this month
      if (payrollRunsRes.status === 'fulfilled' && payrollRunsRes.value.ok && !cancelled) {
        const j = await payrollRunsRes.value.json()
        type PayRun = { period: string; status: string; matched_count: number; ghost_count: number; missing_count: number; discrepancy_count: number }
        const run: PayRun | undefined = (j.data?.runs ?? []).find(
          (r: PayRun) => r.period === month && r.status !== 'pending'
        )
        if (run && !cancelled) {
          setPayrollData({ matched_count: run.matched_count, ghost_count: run.ghost_count, missing_count: run.missing_count, discrepancy_count: run.discrepancy_count })
          setPayrollStatus('done')
        }
      }

      // Close period - restore closed state from audit log
      if (closeRes.status === 'fulfilled' && closeRes.value.ok && !cancelled) {
        const j = await closeRes.value.json()
        if (j.data?.closed) {
          setClosedAt(j.data.closed_at)
          setClosedBy(j.data.closed_by)
        }
      }
    }

    loadRecentResults()
    return () => { cancelled = true }
  }, [month, toolId, getToken])

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
    if (roster.length > 0) {
      setPayrollStatus('running')
      setPayrollData(null)
    }

    const token = await getToken()
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` }

    // Invoice + VAT are synchronous - fire together, pass tool_id so config (grace days, VAT rate) is applied
    const [invRes, vatRes] = await Promise.allSettled([
      fetch(`${API}/reconciliation/invoice-summary?period_start=${start}&period_end=${end}&tool_id=${toolId}`, { headers }),
      fetch(`${API}/reconciliation/vat-summary?period_start=${start}&period_end=${end}&tool_id=${toolId}`, { headers }),
    ])

    if (invRes.status === 'fulfilled' && invRes.value.ok) {
      const j = await invRes.value.json()
      const d = j.data
      setInvoiceData({
        total_invoices:          d.total_invoices,
        total_amount_cents:      d.total_amount_cents,
        total_outstanding_cents: d.total_outstanding_cents,
        total_tax_cents:         d.total_tax_cents,
        flagged_count:           d.flagged?.length ?? 0,
        paid_count:              d.paid_count,
        overdue_count:           d.overdue_count,
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

    // Bank rec is async - enqueue then poll
    try {
      const bankRes = await fetch(`${API}/reconciliation/run`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_start: start, period_end: end, tool_id: toolId }),
      })

      // 409 means a run is already in flight - poll for it rather than erroring
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
          // Check approval table directly - more reliable than reading execution.decision
          try {
            const at = await getToken()
            const apr = await fetch(`${API}/reconciliation/approval-status?period_start=${start}&period_end=${end}`, { headers: { Authorization: `Bearer ${at}` } })
            if (apr.ok) {
              const aData = (await apr.json()).data
              if (aData.approval_status === 'pending') setBankApprovalState('pending')
              else if (aData.approval_status === 'approved') setBankApprovalState('approved')
              else if (aData.approval_status === 'rejected') setBankApprovalState('rejected')
              else setBankApprovalState('none')
            }
          } catch { setBankApprovalState('none') }
        }
      }, 2000)
    } catch {
      setBankStatus('error')
      setAnyRunning(false)
    }

    // Payroll - runs in background if roster is loaded
    if (roster.length > 0) {
      ;(async () => {
        try {
          const pt = await getToken()
          const payRes = await fetch(`${API}/payroll-runs`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${pt}`,
              'Content-Type': 'application/json',
              'Idempotency-Key': `payroll-all-${toolId}-${month}-${Date.now()}`,
            },
            body: JSON.stringify({ period: month, roster, tool_id: toolId }),
          })
          if (!payRes.ok) { setPayrollStatus('error'); return }
          const payJson = await payRes.json()
          const runId: string = payJson.data?.run_id
          if (!runId) { setPayrollStatus('error'); return }

          let attempts = 0
          while (attempts < 30) {
            await new Promise(r => setTimeout(r, 2000))
            const pollToken = await getToken()
            const poll = await fetch(`${API}/payroll-runs/${runId}`, {
              headers: { Authorization: `Bearer ${pollToken}` },
            })
            if (poll.ok) {
              const pollJson = await poll.json()
              const run = pollJson.data
              if (run.status !== 'pending') {
                setPayrollData({
                  matched_count:     run.matched_count ?? 0,
                  ghost_count:       run.ghost_count ?? 0,
                  missing_count:     run.missing_count ?? 0,
                  discrepancy_count: run.discrepancy_count ?? 0,
                })
                setPayrollStatus('done')
                return
              }
            }
            attempts++
          }
          setPayrollStatus('error')
        } catch {
          setPayrollStatus('error')
        }
      })()
    }
  }, [anyRunning, month, toolId, roster, getToken, toast])

  // Poll every 5s while waiting for a pending bank rec approval to be actioned
  useEffect(() => {
    if (bankApprovalState !== 'pending' || !month) {
      if (approvalPollRef.current) { clearInterval(approvalPollRef.current); approvalPollRef.current = null }
      return
    }
    const { start, end } = monthToRange(month)
    approvalPollRef.current = setInterval(async () => {
      try {
        const pt = await getToken()
        const pr = await fetch(`${API}/reconciliation/approval-status?period_start=${start}&period_end=${end}`, { headers: { Authorization: `Bearer ${pt}` } })
        if (!pr.ok) return
        const aData = (await pr.json()).data
        const s = aData.approval_status
        if (s === 'approved') { clearInterval(approvalPollRef.current!); approvalPollRef.current = null; setBankApprovalState('approved') }
        else if (s === 'rejected') { clearInterval(approvalPollRef.current!); approvalPollRef.current = null; setBankApprovalState('rejected') }
      } catch { /* silent - approval polling is best-effort */ }
    }, 5000)
    return () => { if (approvalPollRef.current) { clearInterval(approvalPollRef.current); approvalPollRef.current = null } }
  }, [bankApprovalState, month, getToken])

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
      if (!res.ok) {
        const errJson = await res.json().catch(() => null)
        toast(errJson?.error ?? `Failed to close period (${res.status})`, 'error')
        return
      }
      const json = await res.json()
      setClosedAt(json.data?.closed_at ?? null)
      setClosedBy(json.data?.closed_by ?? null)
      toast(`${monthLabel} closed`, 'success')
    } catch (err) {
      console.error('[close-period]', err)
      toast('Network error - check console for details', 'error')
    } finally {
      setClosing(false)
    }
  }, [month, closing, monthLabel, getToken, toast])

  const reopenPeriod = useCallback(async () => {
    if (!month || reopening) return
    setReopening(true)
    try {
      const { start, end } = monthToRange(month)
      const token = await getToken()
      const res = await fetch(`${API}/reconciliation/reopen-period`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_start: start, period_end: end }),
      })
      if (!res.ok) { toast('Failed to reopen period', 'error'); return }
      setClosedAt(null)
      setClosedBy(null)
      toast(`${monthLabel} reopened`, 'success')
    } catch {
      toast('Network error', 'error')
    } finally {
      setReopening(false)
    }
  }, [month, reopening, monthLabel, getToken, toast])

  const [exportLoading, setExportLoading] = useState<null | 'pdf' | 'google-drive' | 'dropbox' | 'onedrive'>(null)

  const reportPayload = useCallback(() => {
    if (!month) return null
    const { start, end } = monthToRange(month)
    return {
      period_start: start,
      period_end: end,
      month_label: monthLabel,
      currency_symbol: symbol,
      bank: bankData ?? undefined,
      invoice: invoiceData ?? undefined,
      vat: vatData ?? undefined,
      payroll: payrollData ?? undefined,
      closed_at: closedAt ?? undefined,
      closed_by: closedBy ?? undefined,
    }
  }, [month, monthLabel, symbol, bankData, invoiceData, vatData, payrollData, closedAt, closedBy])

  const downloadPDF = useCallback(async () => {
    const payload = reportPayload()
    if (!payload || exportLoading) return
    setExportLoading('pdf')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/reconciliation/pdf`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) { toast('PDF generation failed', 'error'); return }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `reconciliation_${monthLabel.replace(' ', '_')}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast('Network error', 'error')
    } finally {
      setExportLoading(null)
    }
  }, [reportPayload, exportLoading, monthLabel, getToken, toast])

  const cloudExport = useCallback(async (destination: 'google-drive' | 'dropbox' | 'onedrive') => {
    const payload = reportPayload()
    if (!payload || exportLoading) return
    setExportLoading(destination)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/reconciliation/export/${destination}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        toast(j?.detail ?? j?.error ?? `Export failed (${res.status})`, 'error')
        return
      }
      const label = destination === 'google-drive' ? 'Google Drive' : destination === 'dropbox' ? 'Dropbox' : 'OneDrive'
      toast(`Uploaded to ${label}`, 'success')
    } catch {
      toast('Network error', 'error')
    } finally {
      setExportLoading(null)
    }
  }, [reportPayload, exportLoading, getToken, toast])

  const allDone = bankStatus === 'done' && bankApprovalState !== 'pending'
    && invoiceStatus === 'done' && vatStatus === 'done'
    && (roster.length === 0 || payrollStatus === 'done')

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

      {/* Summary grid - 4 cols when roster loaded, 3 otherwise */}
      <div className={`grid gap-3 ${roster.length > 0 ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 sm:grid-cols-3'}`}>
        <SummaryCard title="Bank" accent="#00a8cc" status={bankStatus} onDrillIn={() => onViewAudit('bank_reconciliation:')}>
          {bankData && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Matched"   value={String(bankData.matched_count)} />
              <Stat label="Unmatched" value={String(bankData.unmatched_count)} danger={bankData.unmatched_count > 0} />
              <Stat label="Flagged"   value={String(bankData.flagged_count)}   danger={bankData.flagged_count > 0} />
              <Stat label="Total"     value={String(bankData.total_txn_count)} />
            </div>
          )}
        </SummaryCard>

        <SummaryCard title="Invoices" accent="#f5a623" status={invoiceStatus} onDrillIn={() => onViewAudit('invoice_reconciliation:')}>
          {invoiceData && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Invoices"    value={String(invoiceData.total_invoices)} />
              <Stat label="Flagged"     value={String(invoiceData.flagged_count)}  danger={invoiceData.flagged_count > 0} />
              <Stat label="Tax"         value={fmt(invoiceData.total_tax_cents, symbol)} />
              <Stat label="Outstanding" value={fmt(invoiceData.total_outstanding_cents, symbol)} danger={invoiceData.total_outstanding_cents > 0} />
            </div>
          )}
        </SummaryCard>

        <SummaryCard title="VAT" accent="#00C853" status={vatStatus} onDrillIn={() => onViewAudit('vat_reconciliation:')}>
          {vatData && (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Output VAT" value={fmt(vatData.output_vat_cents, symbol)} />
              <Stat label="Net sales"  value={fmt(vatData.net_sales_cents, symbol)} />
              <Stat label="Position"   value={fmt(vatData.vat_position_cents, symbol)} />
              <Stat label="Flagged"    value={String(vatData.flagged_count)} danger={vatData.flagged_count > 0} />
            </div>
          )}
        </SummaryCard>

        {roster.length > 0 && (
          <SummaryCard title="Payroll" accent="#00a8cc" status={payrollStatus} onDrillIn={() => onViewAudit('payroll_reconciliation:')}>
            {payrollData && (
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Matched"      value={String(payrollData.matched_count)} />
                <Stat label="Ghosts"       value={String(payrollData.ghost_count)}       danger={payrollData.ghost_count > 0} />
                <Stat label="Missing"      value={String(payrollData.missing_count)}      danger={payrollData.missing_count > 0} />
                <Stat label="Discrepancy"  value={String(payrollData.discrepancy_count)}  danger={payrollData.discrepancy_count > 0} />
              </div>
            )}
          </SummaryCard>
        )}
      </div>

      {/* Payroll no-roster fallback */}
      {roster.length === 0 && (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-3 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-0.5">Payroll</p>
            <p className="text-[11px] font-body text-brand-muted">No roster saved - add employees in the Payroll tab to include payroll here.</p>
          </div>
          <span className="text-[11px] font-body text-brand-muted shrink-0 ml-4">Use the Payroll tab →</span>
        </div>
      )}

      {/* Approval state banners */}
      {bankApprovalState === 'pending' && (
        <div className="bg-[rgba(0,168,204,0.06)] border border-[rgba(0,168,204,0.2)] rounded-sm px-4 py-3 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-body uppercase tracking-widest text-[#00a8cc] mb-0.5">Awaiting approval</p>
            <p className="text-xs font-body text-brand-secondary">Bank reconciliation is complete but requires sign-off before you can close the period.</p>
          </div>
          <a href="/approvals" className="shrink-0 ml-4 text-[11px] font-body text-[#00a8cc] hover:underline transition-colors">
            Review in Approvals →
          </a>
        </div>
      )}
      {bankApprovalState === 'rejected' && (
        <div className="bg-[rgba(255,77,109,0.06)] border border-[rgba(255,77,109,0.2)] rounded-sm px-4 py-3 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d] mb-0.5">Reconciliation rejected</p>
            <p className="text-xs font-body text-brand-secondary">The bank reconciliation was rejected. Re-run to try again.</p>
          </div>
          <button
            type="button"
            onClick={() => { setBankApprovalState('none'); setBankStatus('idle'); setBankData(null) }}
            className="shrink-0 ml-4 text-[11px] font-body text-[#ff4d6d] hover:underline transition-colors"
          >
            Re-run →
          </button>
        </div>
      )}

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
        <div className="bg-[rgba(0,200,83,0.06)] border border-[rgba(0,200,83,0.2)] rounded-sm px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="text-[#00C853] text-sm shrink-0">✓</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-body text-[#00C853]">{monthLabel} closed</p>
              <p className="text-[11px] font-body text-brand-muted">
                by {closedBy?.split('@')[0]} · {new Date(closedAt).toLocaleString('en-GB')}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-[rgba(0,200,83,0.15)]">
            <button
              type="button"
              onClick={downloadPDF}
              disabled={exportLoading !== null}
              className="text-[11px] font-body px-3 py-1.5 rounded-sm border border-brand-border text-brand-text bg-transparent hover:bg-brand-elevated transition-colors disabled:opacity-50"
            >
              {exportLoading === 'pdf' ? 'Generating…' : 'Download PDF'}
            </button>
            {(['google-drive', 'dropbox', 'onedrive'] as const).map((dest) => {
              const labels: Record<string, string> = { 'google-drive': 'Google Drive', dropbox: 'Dropbox', onedrive: 'OneDrive' }
              return (
                <button
                  key={dest}
                  type="button"
                  onClick={() => cloudExport(dest)}
                  disabled={exportLoading !== null}
                  className="flex items-center gap-1.5 text-[11px] font-body px-2.5 py-1.5 rounded-sm border border-brand-border bg-brand-surface hover:bg-brand-elevated text-brand-secondary transition-colors disabled:opacity-40"
                >
                  <IntegrationLogo slug={dest} size={13} />
                  {exportLoading === dest ? 'Uploading…' : `Export to ${labels[dest]}`}
                </button>
              )
            })}
            <button
              type="button"
              onClick={reopenPeriod}
              disabled={reopening}
              className="ml-auto text-[11px] font-body px-3 py-1.5 rounded-sm border border-[rgba(255,77,109,0.3)] text-[#ff4d6d] hover:bg-[rgba(255,77,109,0.06)] transition-colors disabled:opacity-40 shrink-0"
            >
              {reopening ? 'Reopening…' : 'Reopen'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
