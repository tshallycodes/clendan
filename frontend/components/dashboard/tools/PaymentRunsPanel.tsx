'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { useToast, useCurrency } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface PaymentRun {
  id: string
  status: string
  scheduled_for: string | null
  processed_at: string | null
  bill_count: number
  total_amount_cents: number
  currency: string
  result?: { mode?: string } | null
  created_at: string
}

const STATUS: Record<string, { label: string; cls: string }> = {
  scheduled: { label: 'Scheduled', cls: 'text-[#00a8cc] bg-[rgba(0,168,204,0.08)] border-[rgba(0,168,204,0.2)]' },
  paid:      { label: 'Paid',      cls: 'text-[#00C853] bg-[rgba(0,200,83,0.08)] border-[rgba(0,200,83,0.2)]' },
  cancelled: { label: 'Cancelled', cls: 'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border-[rgba(255,77,109,0.2)]' },
}

function deadline(iso: string | null): { text: string; urgent: boolean } {
  if (!iso) return { text: '', urgent: false }
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return { text: 'Deadline passed', urgent: true }
  const h = Math.floor(diff / 3_600_000)
  if (h < 48) return { text: `Approve within ${h}h`, urgent: h < 12 }
  return { text: `Approve by ${new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}`, urgent: false }
}

const btn = 'text-[11px] font-body px-3 py-1.5 rounded-sm transition-all active:scale-[0.97] disabled:opacity-40'

export function PaymentRunsPanel({ toolId }: { toolId: string | null }) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const { convert } = useCurrency()
  const [runs, setRuns] = useState<PaymentRun[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<Record<string, string | null>>({})
  const [rescheduleId, setRescheduleId] = useState<string | null>(null)
  const [rescheduleDate, setRescheduleDate] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/payment-runs?limit=50`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) { const j = await res.json(); setRuns(j.data?.runs ?? []) }
    } finally { setLoading(false) }
  }, [getToken])

  useEffect(() => { void load() }, [load])

  async function patch(id: string, action: string, body?: object) {
    setBusy(p => ({ ...p, [id]: action }))
    try {
      const token = await getToken()
      const res = await fetch(`${API}/payment-runs/${id}/${action}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      const j = await res.json().catch(() => ({}))
      if (res.ok) {
        toast(
          action === 'approve' ? 'Payment released' : action === 'cancel' ? 'Run cancelled' : 'Run rescheduled',
          action === 'cancel' ? 'info' : 'success',
        )
        setRescheduleId(null); setRescheduleDate('')
        await load()
      } else {
        toast((j as { error?: string; detail?: string }).error ?? (j as { detail?: string }).detail ?? 'Action failed', 'error')
      }
    } finally { setBusy(p => ({ ...p, [id]: null })) }
  }

  if (!toolId) return null

  return (
    <div className="space-y-4">
      <div className="bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
        <p className="text-[11px] font-body text-brand-muted leading-relaxed">
          <span className="text-brand-secondary">Dry-run mode.</span> Approving a run marks its bills as paid in Clendan so you can see the full flow - no real money moves until live payouts are enabled. Approve before the deadline to release a run; miss it and the run auto-cancels (you can reschedule it).
        </p>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Payment Runs · {runs.length}</p>
        <button type="button" onClick={() => void load()} className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors">Refresh</button>
      </div>

      {loading ? (
        <div className="space-y-2">{[1, 2].map(i => <div key={i} className="h-20 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />)}</div>
      ) : runs.length === 0 ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-12 text-center">
          <p className="text-xs font-body text-brand-muted">No payment runs yet - trigger a run, or wait for the scheduled one, to queue bills for payment.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {runs.map(run => {
            const st = STATUS[run.status] ?? { label: run.status, cls: 'text-brand-muted border-brand-border' }
            const dl = deadline(run.scheduled_for)
            const b = busy[run.id]
            return (
              <motion.div key={run.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
                className="bg-brand-surface border border-brand-border rounded-sm p-4">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2.5">
                      <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${st.cls}`}>{st.label}</span>
                      <span className="text-sm font-body text-brand-text">{convert(run.total_amount_cents, run.currency)}</span>
                      <span className="text-[11px] font-body text-brand-muted">{run.bill_count} {run.bill_count === 1 ? 'bill' : 'bills'}</span>
                    </div>
                    {run.status === 'scheduled' && (
                      <p className={`text-[11px] font-body ${dl.urgent ? 'text-[#f5a623]' : 'text-brand-muted'}`}>{dl.text}</p>
                    )}
                    {run.status === 'paid' && run.processed_at && (
                      <p className="text-[11px] font-body text-brand-muted">
                        Released {new Date(run.processed_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                        {run.result?.mode === 'dry_run' && <span className="text-brand-muted"> · dry-run</span>}
                      </p>
                    )}
                    {run.status === 'cancelled' && (
                      <p className="text-[11px] font-body text-brand-muted">Approval window elapsed</p>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {run.status === 'scheduled' && (
                      <>
                        <button type="button" disabled={!!b} onClick={() => void patch(run.id, 'approve')}
                          className={`${btn} bg-brand-green text-black font-medium hover:bg-[#00a844]`}>
                          {b === 'approve' ? '…' : 'Approve & pay'}
                        </button>
                        <button type="button" disabled={!!b} onClick={() => void patch(run.id, 'cancel')}
                          className={`${btn} border border-brand-border text-brand-muted hover:text-brand-text hover:bg-brand-elevated`}>
                          {b === 'cancel' ? '…' : 'Cancel'}
                        </button>
                      </>
                    )}
                    {run.status === 'cancelled' && rescheduleId !== run.id && (
                      <button type="button" onClick={() => setRescheduleId(run.id)}
                        className={`${btn} border border-brand-border text-brand-text hover:bg-brand-elevated`}>Reschedule</button>
                    )}
                  </div>
                </div>

                {rescheduleId === run.id && (
                  <div className="flex items-center gap-2 mt-3 pt-3 border-t border-brand-border-subtle">
                    <input type="datetime-local" value={rescheduleDate} onChange={e => setRescheduleDate(e.target.value)}
                      className="bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-2.5 py-1.5 text-[11px] font-body text-brand-text outline-none" />
                    <button type="button" disabled={!rescheduleDate || busy[run.id] === 'reschedule'}
                      onClick={() => void patch(run.id, 'reschedule', { scheduled_for: new Date(rescheduleDate).toISOString() })}
                      className={`${btn} bg-brand-green text-black font-medium hover:bg-[#00a844]`}>
                      {busy[run.id] === 'reschedule' ? '…' : 'Confirm'}
                    </button>
                    <button type="button" onClick={() => { setRescheduleId(null); setRescheduleDate('') }}
                      className={`${btn} border border-brand-border text-brand-muted hover:text-brand-text`}>Cancel</button>
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
