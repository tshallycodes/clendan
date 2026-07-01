'use client'

import { useState, useRef, useEffect } from 'react'

interface Props {
  value: string // YYYY-MM
  onChange: (value: string) => void
  className?: string
  placeholder?: string
}

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTH_FULL   = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']

function CalendarIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-brand-muted shrink-0">
      <rect x="1" y="2" width="10" height="9" rx="1" stroke="currentColor" strokeWidth="1" />
      <path d="M1 5h10" stroke="currentColor" strokeWidth="1" />
      <path d="M4 1v2M8 1v2" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
    </svg>
  )
}

export function MonthPicker({ value, onChange, className, placeholder = 'Select month' }: Props) {
  const today = new Date()
  const [open, setOpen] = useState(false)
  const [viewYear, setViewYear] = useState(() =>
    value ? parseInt(value.slice(0, 4)) : today.getFullYear()
  )
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Sync viewYear when value changes externally
  useEffect(() => {
    if (value) setViewYear(parseInt(value.slice(0, 4)))
  }, [value])

  const selectedYear  = value ? parseInt(value.slice(0, 4)) : null
  const selectedMonth = value ? parseInt(value.slice(5, 7)) - 1 : null

  const displayLabel = value
    ? `${MONTH_FULL[parseInt(value.slice(5, 7)) - 1]} ${value.slice(0, 4)}`
    : ''

  function select(monthIndex: number) {
    const m = String(monthIndex + 1).padStart(2, '0')
    onChange(`${viewYear}-${m}`)
    setOpen(false)
  }

  function thisMonth() {
    const m = String(today.getMonth() + 1).padStart(2, '0')
    onChange(`${today.getFullYear()}-${m}`)
    setOpen(false)
  }

  return (
    <div ref={ref} className={`relative ${className ?? ''}`}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 bg-brand-bg border border-brand-border rounded-sm text-brand-text px-3 py-1.5 text-xs font-body focus:outline-none focus:border-[#00C853] w-full hover:bg-brand-elevated transition-colors"
      >
        <span className="flex-1 text-left min-w-[120px]">
          {displayLabel || <span className="text-brand-muted">{placeholder}</span>}
        </span>
        <CalendarIcon />
      </button>

      {open && (
        <div
          className="absolute z-50 top-full mt-1 left-0 bg-brand-surface border border-brand-border rounded-sm p-3 w-56"
          style={{ boxShadow: '0 4px 20px rgba(0,0,0,0.18)' }}
        >
          {/* Year navigation */}
          <div className="flex items-center justify-between mb-3">
            <button
              type="button"
              onClick={() => setViewYear(y => y - 1)}
              className="text-brand-secondary hover:text-brand-text transition-colors w-7 h-7 flex items-center justify-center rounded-sm hover:bg-brand-elevated text-sm"
            >
              ‹
            </button>
            <span className="text-xs font-body text-brand-text font-medium">{viewYear}</span>
            <button
              type="button"
              onClick={() => setViewYear(y => y + 1)}
              className="text-brand-secondary hover:text-brand-text transition-colors w-7 h-7 flex items-center justify-center rounded-sm hover:bg-brand-elevated text-sm"
            >
              ›
            </button>
          </div>

          {/* Month grid */}
          <div className="grid grid-cols-4 gap-1">
            {MONTH_LABELS.map((label, i) => {
              const isSelected = selectedYear === viewYear && selectedMonth === i
              const isCurrentMonth = today.getFullYear() === viewYear && today.getMonth() === i
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => select(i)}
                  className={`text-[12px] font-body py-1.5 rounded-sm transition-colors ${
                    isSelected
                      ? 'bg-[#00C853] text-black font-medium'
                      : isCurrentMonth
                      ? 'border border-brand-border text-brand-text hover:bg-brand-elevated'
                      : 'text-brand-secondary hover:bg-brand-elevated hover:text-brand-text'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>

          {/* Footer actions */}
          <div className="flex justify-between mt-3 pt-2 border-t border-brand-border">
            <button
              type="button"
              onClick={() => { onChange(''); setOpen(false) }}
              className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={thisMonth}
              className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors"
            >
              This month
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
