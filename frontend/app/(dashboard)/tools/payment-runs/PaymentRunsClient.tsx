'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useCurrency, useToast } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { ToolPageShell, ToolResultState, type ToolRenderCtx } from '@/components/dashboard/tools/ToolPageShell'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface BillSummary {
  id: string
  contact_name: string | null
  total_cents: number
  outstanding_cents: number
  due_date: string | null
  action: 'schedule_payment' | 'request_approval' | 'skip'
  reason: string
}

interface Batch {
  id: string
  status: string
  scheduled_for: string | null
  bill_count: number
  total_amount_cents: number
  currency: string
  created_at: string
}

const ACTION_STYLE: Record<string, string> = {
  schedule_payment: 'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
  request_approval: 'text-[#00a8cc] bg-[rgba(0,168,204,0.08)] border-[rgba(0,168,204,0.2)]',
  skip:             'text-brand-muted bg-brand-elevated border-brand-border',
}
const ACTION_LABEL: Record<string, string> = { schedule_payment: 'Schedule', request_approval: 'Needs approval', skip: 'Skip' }
const BATCH_STYLE: Record<string, string> = {
  scheduled: 'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]',
  processed: 'text-brand-secondary bg-brand-elevated border-brand-border',
  cancelled: 'text-brand-muted bg-brand-elevated border-brand-border',
}

function StatCard({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-3">
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{label}</p>
      <p className={`text-lg font-heading font-bold mt-1 tabular-nums ${tone ?? 'text-brand-text'}`}>{value}</p>
    </div>
  )
}

function useMoney() {
  const { currency } = useCurrency()
  const sym = CURRENCY_MAP[currency]?.symbol ?? currency
  return (c: number) => `${sym}${(c / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function Batches() {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const fmt = useMoney()
  const [batches, setBatches] = useState<Batch[]>([])
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/payment-runs?limit=20`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) setBatches(((await res.json()).data?.runs as Batch[]) ?? [])
    } finally {
      setLoading(false)
    }
  }, [getToken])

  useEffect(() => { load() }, [load])

  async function cancel(id: string) {
    setCancelling(id)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/payment-runs/${id}/cancel`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        toast(j?.detail ?? 'Could not cancel', 'error')
        return
      }
      toast('Payment run cancelled', 'success')
      setBatches((prev) => prev.map((b) => (b.id === id ? { ...b, status: 'cancelled' } : b)))
    } catch {
      toast('Network error', 'error')
    } finally {
      setCancelling(null)
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Payment run history</p>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-x-auto">
        <table className="w-full text-xs font-body min-w-[560px]">
          <thead>
            <tr className="border-b border-brand-border">
              <th className="text-left px-4 py-2 text-brand-muted font-normal">Created</th>
              <th className="text-left px-4 py-2 text-brand-muted font-normal">Scheduled for</th>
              <th className="text-right px-4 py-2 text-brand-muted font-normal">Bills</th>
              <th className="text-right px-4 py-2 text-brand-muted font-normal">Total</th>
              <th className="text-left px-4 py-2 text-brand-muted font-normal">Status</th>
              <th className="text-right px-4 py-2 text-brand-muted font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-brand-muted">Loading…</td></tr>
            ) : batches.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-brand-muted">No payment runs yet - create one above.</td></tr>
            ) : batches.map((b) => (
              <tr key={b.id} className="border-t border-brand-border hover:bg-brand-elevated transition-colors">
                <td className="px-4 py-2.5 text-brand-muted">{new Date(b.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
                <td className="px-4 py-2.5 text-brand-secondary">{b.scheduled_for ? new Date(b.scheduled_for).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' }) : '-'}</td>
                <td className="px-4 py-2.5 text-right text-brand-text tabular-nums">{b.bill_count}</td>
                <td className="px-4 py-2.5 text-right text-brand-text tabular-nums">{fmt(b.total_amount_cents)}</td>
                <td className="px-4 py-2.5"><span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${BATCH_STYLE[b.status] ?? 'text-brand-secondary border-brand-border'}`}>{b.status}</span></td>
                <td className="px-4 py-2.5 text-right">
                  {b.status === 'scheduled' && (
                    <button type="button" onClick={() => cancel(b.id)} disabled={cancelling === b.id}
                      className="text-[11px] font-body text-[#ff4d6d] hover:underline disabled:opacity-50">
                      {cancelling === b.id ? '…' : 'Cancel'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Result({ ctx }: { ctx: ToolRenderCtx }) {
  const fmt = useMoney()
  const t = ctx.trace

  if (!ctx.deployed) {
    return <ToolResultState deployed={null} loading={ctx.loading} notDeployedHint="Connect an accounting integration and deploy to schedule supplier payments." />
  }
  if (ctx.loading && !t) {
    return <div className="h-40 bg-brand-elevated rounded-sm animate-pulse" />
  }

  const perBill = (t?.per_bill as BillSummary[] | undefined) ?? []
  const scheduledCount = Number(t?.scheduled_count ?? 0)
  const approvalCount = Number(t?.approval_required_count ?? 0)
  const totalAuto = Number(t?.total_auto_pay_cents ?? 0)
  const totalApproval = Number(t?.total_approval_cents ?? 0)
  const riskFlags = (t?.risk_flags as string[] | undefined) ?? []
  const summary = t?.claude_summary as string | undefined

  return (
    <div className="space-y-5">
      {!t && (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-3 text-center">
          <p className="text-xs font-body text-brand-muted">
            No payment run created yet - click <span className="text-brand-secondary">Create payment run</span> to scan bills due and schedule them.
          </p>
        </div>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="To schedule" value={scheduledCount} tone={scheduledCount ? 'text-[#00C853]' : undefined} />
        <StatCard label="Auto-pay total" value={fmt(totalAuto)} />
        <StatCard label="Needs approval" value={approvalCount} tone={approvalCount ? 'text-[#00a8cc]' : undefined} />
        <StatCard label="Approval total" value={fmt(totalApproval)} />
      </div>

      {(summary || riskFlags.length > 0) && (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-2">
          {summary && <p className="text-xs font-body text-brand-secondary leading-relaxed">{summary}</p>}
          {riskFlags.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-1">
              {riskFlags.map((f, i) => (
                <span key={i} className="text-[11px] font-body px-2 py-0.5 rounded-sm text-[#f5a623] bg-[rgba(245,166,35,0.08)] border border-[rgba(245,166,35,0.2)]">{f}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Bills in this run · {perBill.length}</p>
        <div className="bg-brand-surface border border-brand-border rounded-sm overflow-x-auto">
          <table className="w-full text-xs font-body min-w-[640px]">
            <thead>
              <tr className="border-b border-brand-border">
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Supplier</th>
                <th className="text-right px-4 py-2 text-brand-muted font-normal">Outstanding</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Due</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Action</th>
                <th className="text-left px-4 py-2 text-brand-muted font-normal">Reason</th>
              </tr>
            </thead>
            <tbody>
              {perBill.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-brand-muted">No bills due within the window.</td></tr>
              ) : perBill.map((b) => (
                <tr key={b.id} className="border-t border-brand-border hover:bg-brand-elevated transition-colors align-top">
                  <td className="px-4 py-2.5 text-brand-text">{b.contact_name ?? '-'}</td>
                  <td className="px-4 py-2.5 text-right text-brand-text tabular-nums">{fmt(b.outstanding_cents)}</td>
                  <td className="px-4 py-2.5 text-brand-muted">{b.due_date ? new Date(b.due_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '-'}</td>
                  <td className="px-4 py-2.5"><span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${ACTION_STYLE[b.action]}`}>{ACTION_LABEL[b.action]}</span></td>
                  <td className="px-4 py-2.5 text-brand-secondary max-w-[280px]">{b.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Batches />
    </div>
  )
}

export function PaymentRunsClient() {
  return (
    <ToolPageShell toolSlug="payment-runs" runLabel="Create payment run">
      {(ctx) => <Result ctx={ctx} />}
    </ToolPageShell>
  )
}
