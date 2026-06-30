'use client'

import { useState, useRef, useEffect } from 'react'

interface Props {
  value: string // YYYY-MM-DD
  onChange: (value: string) => void
  className?: string
}

const DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
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

export function DatePicker({ value, onChange, className }: Props) {
  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

  const [open, setOpen] = useState(false)
  const [viewYear, setViewYear] = useState(() => value ? parseInt(value.slice(0, 4)) : today.getFullYear())
  const [viewMonth, setViewMonth] = useState(() => value ? parseInt(value.slice(5, 7)) - 1 : today.getMonth())
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const displayValue = value
    ? `${value.slice(8, 10)}/${value.slice(5, 7)}/${value.slice(0, 4)}`
    : ''

  const firstDow = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const cells: (number | null)[] = [
    ...Array(firstDow).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  function select(day: number) {
    const m = String(viewMonth + 1).padStart(2, '0')
    const d = String(day).padStart(2, '0')
    onChange(`${viewYear}-${m}-${d}`)
    setOpen(false)
  }

  function prevMonth() {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(y => y - 1) }
    else setViewMonth(m => m - 1)
  }
  function nextMonth() {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(y => y + 1) }
    else setViewMonth(m => m + 1)
  }

  return (
    <div ref={ref} className={`relative ${className ?? ''}`}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 bg-brand-bg border border-brand-border rounded-sm text-brand-text px-3 py-2 text-xs font-body focus:outline-none focus:border-[#00C853] w-full hover:bg-brand-bg transition-colors"
      >
        <span className="flex-1 text-left">{displayValue || <span className="text-brand-muted">Select date</span>}</span>
        <CalendarIcon />
      </button>

      {open && (
        <div
          className="absolute z-50 top-full mt-1 left-0 bg-brand-surface border border-brand-border rounded-sm p-3 w-60"
          style={{ boxShadow: 'var(--nav-shadow)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <button type="button" onClick={prevMonth}
              className="text-brand-secondary hover:text-brand-text transition-colors w-7 h-7 flex items-center justify-center rounded-sm hover:bg-brand-bg">
              ↑
            </button>
            <span className="text-xs font-body text-brand-text font-medium">
              {MONTHS[viewMonth]} {viewYear}
            </span>
            <button type="button" onClick={nextMonth}
              className="text-brand-secondary hover:text-brand-text transition-colors w-7 h-7 flex items-center justify-center rounded-sm hover:bg-brand-bg">
              ↓
            </button>
          </div>

          <div className="grid grid-cols-7 mb-1">
            {DAYS.map(d => (
              <div key={d} className="text-[10px] font-body text-brand-muted text-center py-1">{d}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-y-0.5">
            {cells.map((day, i) => {
              if (!day) return <div key={i} />
              const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
              const isSelected = dateStr === value
              const isToday = dateStr === todayStr
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => select(day)}
                  className={`text-[11px] font-body h-7 w-full rounded-sm transition-colors ${
                    isSelected
                      ? 'bg-[#00C853] text-black font-medium'
                      : isToday
                      ? 'border border-brand-border text-brand-text hover:bg-brand-bg'
                      : 'text-brand-secondary hover:bg-brand-bg hover:text-brand-text'
                  }`}
                >
                  {day}
                </button>
              )
            })}
          </div>

          <div className="flex justify-between mt-3 pt-2 border-t border-brand-border">
            <button type="button" onClick={() => { onChange(''); setOpen(false) }}
              className="text-[10px] font-body text-brand-muted hover:text-brand-secondary transition-colors">
              Clear
            </button>
            <button type="button" onClick={() => { onChange(todayStr); setOpen(false) }}
              className="text-[10px] font-body text-brand-muted hover:text-brand-secondary transition-colors">
              Today
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
