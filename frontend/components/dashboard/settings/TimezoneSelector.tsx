'use client'

import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useTimezone } from '@/components/Providers'
import { useToast } from '@/components/Providers'

const TIMEZONES: { value: string; label: string; region: string }[] = [
  { value: 'UTC',                  label: 'UTC',                        region: 'Universal' },
  { value: 'Europe/London',        label: 'London (GMT / BST)',          region: 'Europe' },
  { value: 'Europe/Dublin',        label: 'Dublin (GMT / IST)',          region: 'Europe' },
  { value: 'Europe/Paris',         label: 'Paris (CET / CEST)',          region: 'Europe' },
  { value: 'Europe/Berlin',        label: 'Berlin (CET / CEST)',         region: 'Europe' },
  { value: 'Europe/Amsterdam',     label: 'Amsterdam (CET / CEST)',      region: 'Europe' },
  { value: 'Europe/Zurich',        label: 'Zurich (CET / CEST)',         region: 'Europe' },
  { value: 'Europe/Stockholm',     label: 'Stockholm (CET / CEST)',      region: 'Europe' },
  { value: 'Europe/Warsaw',        label: 'Warsaw (CET / CEST)',         region: 'Europe' },
  { value: 'America/New_York',     label: 'New York (ET)',               region: 'Americas' },
  { value: 'America/Chicago',      label: 'Chicago (CT)',                region: 'Americas' },
  { value: 'America/Denver',       label: 'Denver (MT)',                 region: 'Americas' },
  { value: 'America/Los_Angeles',  label: 'Los Angeles (PT)',            region: 'Americas' },
  { value: 'America/Toronto',      label: 'Toronto (ET)',                region: 'Americas' },
  { value: 'America/Vancouver',    label: 'Vancouver (PT)',              region: 'Americas' },
  { value: 'America/Sao_Paulo',    label: 'São Paulo (BRT)',             region: 'Americas' },
  { value: 'Africa/Lagos',         label: 'Lagos (WAT)',                 region: 'Africa' },
  { value: 'Africa/Johannesburg',  label: 'Johannesburg (SAST)',         region: 'Africa' },
  { value: 'Africa/Nairobi',       label: 'Nairobi (EAT)',               region: 'Africa' },
  { value: 'Asia/Dubai',           label: 'Dubai (GST)',                 region: 'Middle East & Asia' },
  { value: 'Asia/Riyadh',          label: 'Riyadh (AST)',                region: 'Middle East & Asia' },
  { value: 'Asia/Kolkata',         label: 'Mumbai / Delhi (IST)',        region: 'Middle East & Asia' },
  { value: 'Asia/Singapore',       label: 'Singapore (SGT)',             region: 'Middle East & Asia' },
  { value: 'Asia/Hong_Kong',       label: 'Hong Kong (HKT)',             region: 'Middle East & Asia' },
  { value: 'Asia/Shanghai',        label: 'Shanghai (CST)',              region: 'Middle East & Asia' },
  { value: 'Asia/Tokyo',           label: 'Tokyo (JST)',                 region: 'Middle East & Asia' },
  { value: 'Asia/Seoul',           label: 'Seoul (KST)',                 region: 'Middle East & Asia' },
  { value: 'Australia/Sydney',     label: 'Sydney (AEST / AEDT)',        region: 'Pacific' },
  { value: 'Australia/Melbourne',  label: 'Melbourne (AEST / AEDT)',     region: 'Pacific' },
  { value: 'Pacific/Auckland',     label: 'Auckland (NZST / NZDT)',      region: 'Pacific' },
]

const REGIONS = ['Universal', 'Europe', 'Americas', 'Africa', 'Middle East & Asia', 'Pacific']

export function TimezoneSelector() {
  const { timezone, setTimezone } = useTimezone()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [saving, setSaving] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  const selected = TIMEZONES.find(t => t.value === timezone) ?? TIMEZONES[0]

  const normalised = search.toLowerCase()
  const filtered = normalised
    ? TIMEZONES.filter(t =>
        t.value.toLowerCase().includes(normalised) ||
        t.label.toLowerCase().includes(normalised) ||
        t.region.toLowerCase().includes(normalised)
      )
    : null

  async function handleSelect(value: string) {
    if (value === timezone) { setOpen(false); setSearch(''); return }
    setSaving(true)
    setOpen(false)
    setSearch('')
    try {
      await setTimezone(value)
      toast(`Timezone changed to ${TIMEZONES.find(t => t.value === value)?.label ?? value}`, 'success')
    } catch {
      toast('Failed to save timezone preference', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => { setOpen(v => !v); setTimeout(() => searchRef.current?.focus(), 50) }}
        disabled={saving}
        className="w-full flex items-center justify-between gap-3 bg-brand-bg border border-brand-border rounded-sm px-3 py-2 text-xs font-mono text-brand-text hover:bg-brand-elevated transition-colors disabled:opacity-50"
      >
        <span className="truncate">{selected.label}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.15 }} className="text-brand-muted shrink-0 text-[10px]">▼</motion.span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute z-50 top-full left-0 right-0 mt-1 bg-brand-elevated border border-brand-border rounded-sm overflow-hidden"
          >
            <div className="border-b border-brand-border p-2">
              <input
                ref={searchRef}
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search timezones…"
                className="w-full bg-brand-bg border border-brand-border rounded-sm px-3 py-1.5 text-xs font-mono text-brand-text placeholder:text-brand-muted focus:border-[#00C853] focus:outline-none"
              />
            </div>
            <div className="max-h-64 overflow-y-auto">
              {filtered ? (
                filtered.length === 0 ? (
                  <p className="px-3 py-4 text-xs font-mono text-brand-muted text-center">No results for &ldquo;{search}&rdquo;</p>
                ) : (
                  filtered.map(tz => (
                    <TzOption key={tz.value} tz={tz} selected={tz.value === timezone} onSelect={handleSelect} />
                  ))
                )
              ) : (
                REGIONS.map(region => {
                  const group = TIMEZONES.filter(t => t.region === region)
                  if (!group.length) return null
                  return (
                    <div key={region}>
                      <p className="px-3 pt-3 pb-1 text-[10px] font-mono uppercase tracking-widest text-brand-muted">{region}</p>
                      {group.map(tz => (
                        <TzOption key={tz.value} tz={tz} selected={tz.value === timezone} onSelect={handleSelect} />
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
  )
}

function TzOption({ tz, selected, onSelect }: { tz: typeof TIMEZONES[0]; selected: boolean; onSelect: (v: string) => void }) {
  return (
    <button
      onClick={() => onSelect(tz.value)}
      className={`w-full flex items-center gap-3 px-3 py-2 text-left text-xs font-mono transition-colors ${
        selected ? 'bg-[rgba(0,200,83,0.08)] text-[#00C853]' : 'text-brand-text hover:bg-brand-surface'
      }`}
    >
      <span className="flex-1 truncate">{tz.label}</span>
      <span className="text-brand-muted text-[10px] font-mono shrink-0">{tz.value}</span>
      {selected && <span className="text-[#00C853] text-[10px] shrink-0">✓</span>}
    </button>
  )
}
