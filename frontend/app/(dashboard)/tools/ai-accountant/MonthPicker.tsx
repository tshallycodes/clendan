'use client'

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function MonthPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const parsed = value ? value.split('-') : null
  const selYear = parsed ? parseInt(parsed[0]) : new Date().getFullYear()
  const selMonth = parsed ? parseInt(parsed[1]) - 1 : -1
  const [viewYear, setViewYear] = useState(selYear)

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [open])

  function select(monthIdx: number) {
    const mm = String(monthIdx + 1).padStart(2, '0')
    onChange(`${viewYear}-${mm}`)
    setOpen(false)
  }

  const displayLabel = value
    ? new Date(selYear, selMonth).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
    : 'Select period'

  return (
    <div ref={containerRef} className="relative w-fit">
      <button
        type="button"
        onClick={() => setOpen(p => !p)}
        className="flex items-center gap-2 bg-brand-bg border border-brand-border hover:border-[#00C853] text-brand-text text-xs font-mono rounded-sm px-3 py-2 outline-none transition-colors"
      >
        {displayLabel}
        <svg
          width="10" height="6" viewBox="0 0 10 6" fill="none"
          className={`transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        >
          <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full mt-1 z-50 bg-brand-surface border border-brand-border rounded-sm p-3 w-52"
          >
            {/* Year navigation */}
            <div className="flex items-center justify-between mb-3">
              <button
                type="button"
                onClick={() => setViewYear(y => y - 1)}
                className="text-brand-muted hover:text-brand-text text-sm font-mono px-1 transition-colors"
              >
                ‹
              </button>
              <span className="text-xs font-mono text-brand-text">{viewYear}</span>
              <button
                type="button"
                onClick={() => setViewYear(y => y + 1)}
                className="text-brand-muted hover:text-brand-text text-sm font-mono px-1 transition-colors"
              >
                ›
              </button>
            </div>

            {/* Month grid */}
            <div className="grid grid-cols-3 gap-1">
              {MONTHS.map((m, i) => {
                const isActive = viewYear === selYear && i === selMonth
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => select(i)}
                    className={`text-[11px] font-mono rounded-sm px-2 py-1.5 transition-colors ${
                      isActive
                        ? 'bg-[#00C853] text-black'
                        : 'text-brand-text hover:bg-brand-elevated'
                    }`}
                  >
                    {m}
                  </button>
                )
              })}
            </div>

            {/* Quick actions */}
            <div className="flex justify-between mt-3 pt-2 border-t border-brand-border">
              <button
                type="button"
                onClick={() => { onChange(''); setOpen(false) }}
                className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => {
                  const now = new Date()
                  onChange(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
                  setOpen(false)
                }}
                className="text-[10px] font-mono text-[#00C853] hover:text-[#00a844] transition-colors"
              >
                This month
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
