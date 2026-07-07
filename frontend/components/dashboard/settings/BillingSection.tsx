'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Subscription {
  plan: string
  status: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  has_subscription: boolean
}

interface PlanDef {
  id: string
  name: string
  price: string
  blurb: string
  selfServe: boolean
}

// Display metadata only — Stripe Price IDs are the source of truth on the backend.
// Mirrors the marketing pricing tiers.
const PLANS: PlanDef[] = [
  { id: 'starter', name: 'Starter', price: '£299/mo', blurb: '2 tools · 500 executions/mo', selfServe: true },
  { id: 'growth', name: 'Growth', price: '£799/mo', blurb: '5 tools · 5,000 executions/mo', selfServe: true },
  { id: 'enterprise', name: 'Enterprise', price: 'Custom', blurb: 'Unlimited · SLA · SOC 2', selfServe: false },
]

const PLAN_RANK: Record<string, number> = { free: 0, starter: 1, growth: 2, enterprise: 3 }

function StatusBadge({ plan, status }: { plan: string; status: string | null }) {
  const label = plan.charAt(0).toUpperCase() + plan.slice(1)
  const cls =
    status === 'active' || status === 'trialing'
      ? 'text-brand-green border-brand-green/30 bg-[rgba(0,200,83,0.08)]'
      : status === 'past_due'
        ? 'text-[#ff4d6d] border-[#ff4d6d]/30 bg-[rgba(255,77,109,0.08)]'
        : 'text-[#00a8cc] border-[#00a8cc]/30 bg-[rgba(0,168,204,0.08)]'
  return (
    <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border ${cls}`}>{label}</span>
  )
}

export function BillingSection() {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [sub, setSub] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [pending, setPending] = useState<string | null>(null) // plan id or 'portal'

  const load = useCallback(async () => {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/billing/subscription`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const json = await res.json()
      setSub(json.data as Subscription)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [getToken])

  useEffect(() => { load() }, [load])

  // Handle Stripe Checkout return states (?billing=success|canceled)
  useEffect(() => {
    const billing = new URLSearchParams(window.location.search).get('billing')
    if (!billing) return
    window.history.replaceState(null, '', window.location.pathname)
    if (billing === 'success') {
      toast('Subscription updated', 'success')
      // Webhook may lag a moment behind the redirect — refetch shortly after.
      setTimeout(() => { load() }, 2500)
    } else if (billing === 'canceled') {
      toast('Checkout canceled', 'error')
    }
  }, [load, toast])

  async function redirectTo(path: string, key: string, body?: unknown) {
    setPending(key)
    try {
      const token = await getToken()
      const res = await fetch(`${API}${path}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.detail || `${res.status}`)
      }
      const json = await res.json()
      const url = json.data?.url
      if (!url) throw new Error('No redirect URL')
      window.location.href = url
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Something went wrong', 'error')
      setPending(null)
    }
  }

  if (loading) {
    return <div className="h-24 bg-brand-elevated rounded-sm animate-pulse" />
  }

  if (error || !sub) {
    return <p className="text-xs font-body text-brand-muted">Billing unavailable — backend not reachable.</p>
  }

  const currentRank = PLAN_RANK[sub.plan] ?? 0
  const periodEnd = sub.current_period_end
    ? new Date(sub.current_period_end).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
    : null

  return (
    <div className="space-y-5">
      {/* Current plan */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs font-body text-brand-text">Current plan</span>
        <StatusBadge plan={sub.plan} status={sub.status} />
        {sub.status && sub.plan !== 'free' && (
          <span className="text-[11px] font-body text-brand-muted capitalize">{sub.status.replace('_', ' ')}</span>
        )}
      </div>

      {periodEnd && (
        <p className="text-[11px] font-body text-brand-muted">
          {sub.cancel_at_period_end ? (
            <span className="text-[#f5a623]">Cancels on {periodEnd}</span>
          ) : (
            <>Renews on {periodEnd}</>
          )}
        </p>
      )}

      {/* Plan options */}
      <div className="divide-y divide-brand-border border border-brand-border rounded-sm">
        {PLANS.map((p) => {
          const isCurrent = sub.plan === p.id
          const rank = PLAN_RANK[p.id] ?? 0
          const action = rank > currentRank ? 'Upgrade' : 'Switch'
          return (
            <div key={p.id} className="flex items-center justify-between gap-3 px-3 py-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-body text-brand-text">{p.name}</span>
                  <span className="text-[11px] font-body text-brand-muted">{p.price}</span>
                </div>
                <p className="text-[11px] font-body text-brand-muted mt-0.5">{p.blurb}</p>
              </div>
              {isCurrent ? (
                <span className="text-[11px] font-body text-brand-muted shrink-0">Current</span>
              ) : p.selfServe ? (
                <button
                  onClick={() => redirectTo('/billing/checkout', p.id, { plan: p.id })}
                  disabled={pending !== null}
                  className="shrink-0 border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 text-[11px] font-body disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  {pending === p.id ? 'Redirecting…' : action}
                </button>
              ) : (
                <a
                  href="mailto:sales@clendan.com"
                  className="shrink-0 border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 text-[11px] font-body transition-colors"
                >
                  Contact sales
                </a>
              )}
            </div>
          )
        })}
      </div>

      {/* Manage billing (Stripe Customer Portal) */}
      {sub.has_subscription && (
        <button
          onClick={() => redirectTo('/billing/portal', 'portal')}
          disabled={pending !== null}
          className="inline-flex items-center bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-body disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {pending === 'portal' ? 'Opening…' : 'Manage billing'}
        </button>
      )}

      <p className="text-[11px] font-body text-brand-muted">
        Payments are processed securely by Stripe. Manage payment methods, invoices, and cancellation from the billing portal.
      </p>
    </div>
  )
}
