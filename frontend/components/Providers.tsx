'use client'

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { formatCurrency } from '@/lib/currency'

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

interface ThemeCtx {
  theme: string
  setTheme: (t: string) => void
}

const ThemeContext = createContext<ThemeCtx>({ theme: 'dark', setTheme: () => {} })

export function useTheme() {
  return useContext(ThemeContext)
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: string
  message: string
  type: ToastType
}

interface ToastCtx {
  toast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastCtx>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

function ToastItem({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    timerRef.current = setTimeout(() => onDismiss(item.id), 4000)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [item.id, onDismiss])

  const accent =
    item.type === 'error' ? '#ff4d6d'
    : item.type === 'success' ? '#00C853'
    : undefined

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 4, scale: 0.97 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="flex items-start gap-3 bg-brand-surface border border-brand-border rounded-sm px-4 py-3 shadow-none min-w-[280px] max-w-[360px]"
      style={accent ? { borderColor: `${accent}33` } : undefined}
    >
      {accent && (
        <span className="mt-0.5 shrink-0 text-xs font-body font-bold leading-none" style={{ color: accent }}>
          {item.type === 'error' ? '✕' : '✓'}
        </span>
      )}
      <p className="text-xs font-body text-brand-text leading-relaxed flex-1">{item.message}</p>
      <button
        onClick={() => onDismiss(item.id)}
        className="shrink-0 text-brand-muted hover:text-brand-text transition-colors text-xs leading-none mt-0.5"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Timezone
// ---------------------------------------------------------------------------

interface TimezoneCtx {
  timezone: string
  setTimezone: (tz: string) => Promise<void>
}

const TimezoneContext = createContext<TimezoneCtx>({
  timezone: 'UTC',
  setTimezone: async () => {},
})

export function useTimezone() {
  return useContext(TimezoneContext)
}

// ---------------------------------------------------------------------------
// Currency
// ---------------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface CurrencyCtx {
  currency: string
  setCurrency: (code: string) => Promise<void>
  rates: Record<string, number>
  ratesUpdatedAt: string | null
  isStale: boolean
  /** Format amountMinor (stored units) from sourceCurrency into the user's preferred currency. */
  convert: (amountMinor: number, sourceCurrency: string) => string
}

const CurrencyContext = createContext<CurrencyCtx>({
  currency: 'USD',
  setCurrency: async () => {},
  rates: {},
  ratesUpdatedAt: null,
  isStale: false,
  convert: (amountMinor, sourceCurrency) =>
    formatCurrency(amountMinor, sourceCurrency, 'USD', {}),
})

export function useCurrency() {
  return useContext(CurrencyContext)
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

export function Providers({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState('dark')
  const [toasts, setToasts] = useState<ToastItem[]>([])

  // Currency + Timezone state
  const { getToken } = useAuth()
  const [currency, setCurrencyState] = useState('USD')
  const [rates, setRates] = useState<Record<string, number>>({})
  const [ratesUpdatedAt, setRatesUpdatedAt] = useState<string | null>(null)
  const [isStale, setIsStale] = useState(false)
  const [timezone, setTimezoneState] = useState('UTC')

  useEffect(() => {
    const saved = localStorage.getItem('theme') ?? 'dark'
    setThemeState(saved)
  }, [])

  // Fetch rates, currency preference, and tenant timezone once auth is available
  useEffect(() => {
    let cancelled = false
    async function load() {
      const token = await getToken().catch(() => null)
      if (!token || cancelled) return
      try {
        const [ratesRes, prefRes, tenantRes] = await Promise.all([
          fetch(`${API_BASE}/currency/rates`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API_BASE}/currency/preferences`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API_BASE}/tenants/me`, { headers: { Authorization: `Bearer ${token}` } }),
        ])
        if (ratesRes.ok) {
          const ratesJson = await ratesRes.json()
          if (!cancelled) {
            setRates(ratesJson.data?.rates ?? {})
            setRatesUpdatedAt(ratesJson.data?.updated_at ?? null)
            setIsStale(ratesJson.data?.is_stale ?? false)
          }
        }
        if (prefRes.ok) {
          const prefJson = await prefRes.json()
          const saved = prefJson.data?.preferred_currency
          if (!cancelled && saved) {
            setCurrencyState(saved)
            localStorage.setItem('preferredCurrency', saved)
          }
        }
        if (tenantRes.ok) {
          const tenantJson = await tenantRes.json()
          const tz = tenantJson.data?.tenant?.timezone
          if (!cancelled && tz) {
            setTimezoneState(tz)
            localStorage.setItem('timezone', tz)
          }
        }
      } catch {
        // Network error — use localStorage fallbacks
        const localCurrency = localStorage.getItem('preferredCurrency')
        if (!cancelled && localCurrency) setCurrencyState(localCurrency)
        const localTz = localStorage.getItem('timezone')
        if (!cancelled && localTz) setTimezoneState(localTz)
      }
    }
    load()
    return () => { cancelled = true }
  }, [getToken])

  function setTheme(t: string) {
    setThemeState(t)
    localStorage.setItem('theme', t)
    document.documentElement.classList.toggle('dark', t === 'dark')
  }

  const setCurrency = useCallback(async (code: string) => {
    setCurrencyState(code)
    localStorage.setItem('preferredCurrency', code)
    const token = await getToken().catch(() => null)
    if (!token) return
    await fetch(`${API_BASE}/currency/preferences`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ currency: code }),
    }).catch(() => {})
  }, [getToken])

  const setTimezone = useCallback(async (tz: string) => {
    setTimezoneState(tz)
    localStorage.setItem('timezone', tz)
    const token = await getToken().catch(() => null)
    if (!token) return
    await fetch(`${API_BASE}/tenants/me`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ timezone: tz }),
    }).catch(() => {})
  }, [getToken])

  const convert = useCallback(
    (amountMinor: number, sourceCurrency: string) =>
      formatCurrency(amountMinor, sourceCurrency, currency, rates),
    [currency, rates]
  )

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).slice(2, 9)
    setToasts((prev) => [...prev.slice(-4), { id, message, type }])
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <ToastContext.Provider value={{ toast }}>
        <TimezoneContext.Provider value={{ timezone, setTimezone }}>
        <CurrencyContext.Provider value={{ currency, setCurrency, rates, ratesUpdatedAt, isStale, convert }}>
          {children}
          <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 items-end pointer-events-none">
            <AnimatePresence mode="popLayout">
              {toasts.map((item) => (
                <div key={item.id} className="pointer-events-auto">
                  <ToastItem item={item} onDismiss={dismiss} />
                </div>
              ))}
            </AnimatePresence>
          </div>
        </CurrencyContext.Provider>
        </TimezoneContext.Provider>
      </ToastContext.Provider>
    </ThemeContext.Provider>
  )
}
