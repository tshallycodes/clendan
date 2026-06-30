'use client'

import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useCurrency } from '@/components/Providers'
import { useToast } from '@/components/Providers'
import { CURRENCIES, CURRENCY_MAP, CURRENCY_GROUPS, REGION_ORDER, type Currency } from '@/lib/currency'

export function CurrencySelector() {
  const { currency, setCurrency, isStale, ratesUpdatedAt } = useCurrency()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [saving, setSaving] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  const selected = CURRENCY_MAP[currency] ?? CURRENCIES[0]

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setSearch('')
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  // Focus search when opening
  useEffect(() => {
    if (open) setTimeout(() => searchRef.current?.focus(), 50)
  }, [open])

  const normalised = search.toLowerCase()
  const filtered: Currency[] = normalised
    ? CURRENCIES.filter(
        (c) =>
          c.code.toLowerCase().includes(normalised) ||
          c.name.toLowerCase().includes(normalised) ||
          c.region.toLowerCase().includes(normalised)
      )
    : []

  async function handleSelect(code: string) {
    if (code === currency) { setOpen(false); setSearch(''); return }
    setSaving(true)
    setOpen(false)
    setSearch('')
    try {
      await setCurrency(code)
      toast(`Display currency changed to ${code}`, 'success')
    } catch {
      toast('Failed to save currency preference', 'error')
    } finally {
      setSaving(false)
    }
  }

  const staleMessage = isStale && ratesUpdatedAt
    ? `Rates last updated ${new Date(ratesUpdatedAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })} — exchange data may be stale`
    : null

  return (
    <div className="space-y-2">
      {/* Trigger */}
      <div ref={containerRef} className="relative">
        <button
          onClick={() => setOpen((v) => !v)}
          disabled={saving}
          className="w-full flex items-center justify-between gap-3 bg-brand-bg border border-brand-border rounded-sm px-3 py-2 text-xs font-body text-brand-text hover:bg-brand-bg transition-colors disabled:opacity-50"
        >
          <span className="flex items-center gap-2 min-w-0">
            <span className="text-brand-muted shrink-0">{selected.symbol}</span>
            <span className="truncate">{selected.code} — {selected.name}</span>
          </span>
          <motion.span
            animate={{ rotate: open ? 180 : 0 }}
            transition={{ duration: 0.15 }}
            className="text-brand-muted shrink-0 text-[11px]"
          >
            ▼
          </motion.span>
        </button>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className="absolute z-50 top-full left-0 right-0 mt-1 bg-brand-elevated border border-brand-border rounded-sm shadow-none overflow-hidden"
            >
              {/* Search */}
              <div className="border-b border-brand-border p-2">
                <input
                  ref={searchRef}
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search currencies..."
                  className="w-full bg-brand-bg border border-brand-border rounded-sm px-3 py-1.5 text-xs font-body text-brand-text placeholder:text-brand-muted focus:border-[#00C853] focus:outline-none"
                />
              </div>

              {/* Results */}
              <div className="max-h-64 overflow-y-auto">
                {normalised ? (
                  filtered.length === 0 ? (
                    <p className="px-3 py-4 text-xs font-body text-brand-muted text-center">No results for &ldquo;{search}&rdquo;</p>
                  ) : (
                    filtered.map((c) => (
                      <CurrencyOption key={c.code} currency={c} selected={c.code === currency} onSelect={handleSelect} />
                    ))
                  )
                ) : (
                  REGION_ORDER.map((region) => {
                    const group = CURRENCY_GROUPS[region]
                    if (!group?.length) return null
                    return (
                      <div key={region}>
                        <p className="px-3 pt-3 pb-1 text-[11px] font-body uppercase tracking-widest text-brand-muted">
                          {region}
                        </p>
                        {group.map((c) => (
                          <CurrencyOption key={c.code} currency={c} selected={c.code === currency} onSelect={handleSelect} />
                        ))}
                      </div>
                    )
                  })
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Staleness indicator */}
      <AnimatePresence>
        {staleMessage && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="text-[11px] font-body text-[#f5a623] leading-relaxed"
          >
            ⚠ {staleMessage}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}

function CurrencyOption({
  currency,
  selected,
  onSelect,
}: {
  currency: Currency
  selected: boolean
  onSelect: (code: string) => void
}) {
  return (
    <button
      onClick={() => onSelect(currency.code)}
      className={`w-full flex items-center gap-3 px-3 py-2 text-left text-xs font-body transition-colors ${
        selected
          ? 'bg-[rgba(0,200,83,0.08)] text-[#00C853]'
          : 'text-brand-text hover:bg-brand-surface'
      }`}
    >
      <span className="w-8 shrink-0 text-brand-muted">{currency.symbol}</span>
      <span className="w-10 shrink-0 font-semibold">{currency.code}</span>
      <span className="truncate text-brand-secondary">{currency.name}</span>
      {selected && <span className="ml-auto text-[#00C853] text-[11px]">✓</span>}
    </button>
  )
}
