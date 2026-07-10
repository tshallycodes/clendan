'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { CaretDown, Buildings, Check } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/** localStorage / cookie key for the firm member's currently active client tenant. */
export const ACTIVE_CLIENT_KEY = 'clendan_active_client'
const ACTIVE_CLIENT_EVENT = 'clendan:active-client-changed'

export interface FirmClient {
  tenant_id: string
  name: string
  firm_id: string | null
  pending_approvals: number
  connected_integrations: number
}

/** Read the active client tenant id (client-side only). */
export function getActiveClient(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(ACTIVE_CLIENT_KEY)
}

/**
 * Persist the active client tenant. Stored in localStorage (per the app convention) and
 * mirrored to a same-site cookie so server-rendered requests can forward the
 * `X-Clendan-Client` header once the shared API layer is wired to it. Passing null clears
 * the selection (the firm member acts as their own workspace again).
 */
export function setActiveClient(tenantId: string | null): void {
  if (typeof window === 'undefined') return
  if (tenantId) {
    window.localStorage.setItem(ACTIVE_CLIENT_KEY, tenantId)
    document.cookie = `${ACTIVE_CLIENT_KEY}=${encodeURIComponent(tenantId)}; path=/; max-age=2592000; samesite=lax`
  } else {
    window.localStorage.removeItem(ACTIVE_CLIENT_KEY)
    document.cookie = `${ACTIVE_CLIENT_KEY}=; path=/; max-age=0; samesite=lax`
  }
  window.dispatchEvent(new CustomEvent(ACTIVE_CLIENT_EVENT, { detail: tenantId }))
}

/** Fetch the firm's client portfolio. Empty for non-firm users (they have no firm). */
export function useFirmClients(): { clients: FirmClient[]; loading: boolean } {
  const { getToken } = useAuth()
  const [clients, setClients] = useState<FirmClient[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getToken()
      .then((token) => {
        if (!token) {
          if (active) setLoading(false)
          return
        }
        return fetch(`${API_BASE}/firms/clients`, {
          headers: { Authorization: `Bearer ${token}` },
        })
          .then((r) => (r.ok ? r.json() : null))
          .then((j) => {
            if (active) setClients(j?.data?.clients ?? [])
          })
          .catch(() => {})
          .finally(() => {
            if (active) setLoading(false)
          })
      })
      .catch(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [getToken])

  return { clients, loading }
}

/**
 * Top-bar dropdown for firm members to switch the active client tenant. Renders nothing for
 * non-firm users (no clients), degrading gracefully. Switching persists the selection, records
 * the act-as server-side (authorised + audited), and refreshes.
 */
export function ClientSwitcher() {
  const router = useRouter()
  const { getToken } = useAuth()
  const { clients } = useFirmClients()
  const [open, setOpen] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setActiveId(getActiveClient())
    function sync(e: Event) {
      setActiveId((e as CustomEvent).detail ?? null)
    }
    window.addEventListener(ACTIVE_CLIENT_EVENT, sync)
    return () => window.removeEventListener(ACTIVE_CLIENT_EVENT, sync)
  }, [])

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  // Non-firm users have nothing to switch — render no top bar at all.
  if (clients.length === 0) return null

  const active = clients.find((c) => c.tenant_id === activeId) ?? null

  async function select(client: FirmClient | null) {
    setOpen(false)
    setActiveClient(client?.tenant_id ?? null)
    setActiveId(client?.tenant_id ?? null)
    if (client) {
      try {
        const token = await getToken()
        if (token) {
          await fetch(`${API_BASE}/firms/clients/${client.tenant_id}/act-as`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          })
        }
      } catch {
        /* act-as is best-effort here; selection is already persisted */
      }
    }
    router.refresh()
  }

  return (
    <div className="hidden lg:flex items-center justify-end px-6 h-14 border-b border-brand-border bg-brand-surface shrink-0">
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 px-3 py-1.5 border border-brand-border rounded-sm text-xs font-body text-brand-text hover:bg-brand-elevated transition-colors"
        >
          <Buildings className="w-3.5 h-3.5 text-brand-muted shrink-0" />
          <span className="max-w-[180px] truncate">{active ? active.name : 'My workspace'}</span>
          <CaretDown className={cn('w-3 h-3 text-brand-muted transition-transform', open && 'rotate-180')} />
        </button>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
              className="absolute right-0 mt-2 w-64 bg-brand-surface border border-brand-border rounded-[4px] overflow-hidden z-50"
              style={{ boxShadow: 'var(--nav-shadow-raised)' }}
            >
              <div className="px-3 py-2 border-b border-brand-border">
                <span className="text-[10px] font-body uppercase tracking-widest text-brand-muted">
                  Switch client
                </span>
              </div>
              <div className="max-h-80 overflow-y-auto divide-y divide-brand-border">
                <button
                  type="button"
                  onClick={() => select(null)}
                  className="w-full flex items-center justify-between gap-3 px-3 py-2.5 hover:bg-brand-elevated transition-colors text-left"
                >
                  <span className="text-xs font-body text-brand-text">My workspace</span>
                  {active === null && <Check className="w-3.5 h-3.5 text-brand-green shrink-0" />}
                </button>
                {clients.map((c) => (
                  <button
                    key={c.tenant_id}
                    type="button"
                    onClick={() => select(c)}
                    className="w-full flex items-center justify-between gap-3 px-3 py-2.5 hover:bg-brand-elevated transition-colors text-left"
                  >
                    <span className="min-w-0">
                      <span className="block text-xs font-body text-brand-text truncate">{c.name}</span>
                      <span className="block text-[10px] font-body text-brand-muted mt-0.5">
                        {c.pending_approvals} pending · {c.connected_integrations} connected
                      </span>
                    </span>
                    {activeId === c.tenant_id && <Check className="w-3.5 h-3.5 text-brand-green shrink-0" />}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
