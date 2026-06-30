'use client'

import { useState, useRef, useEffect } from 'react'
import { CaretDown } from '@phosphor-icons/react'

export interface SelectOption {
  value: string
  label: string
}

interface SelectProps {
  value: string
  options: SelectOption[]
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

export function Select({ value, options, onChange, placeholder, className }: SelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selected = options.find(o => o.value === value)
  const displayLabel = selected?.label ?? placeholder ?? ''

  return (
    <div ref={ref} className={`relative w-full${className ? ` ${className}` : ''}`}>
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        className={`w-full flex items-center justify-between bg-brand-bg border rounded-sm px-3 py-2 text-xs font-body text-brand-text outline-none transition-colors ${open ? 'border-[#00C853]' : 'border-brand-border'}`}
      >
        <span className={selected ? 'text-brand-text' : 'text-brand-muted'}>{displayLabel}</span>
        <CaretDown
          size={12}
          className={`shrink-0 ml-2 text-brand-muted transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="absolute top-full left-0 right-0 z-50 mt-px bg-brand-elevated border border-brand-border rounded-sm">
          {options.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                onChange(opt.value)
                setOpen(false)
              }}
              className={`w-full text-left px-3 py-2 text-xs font-body transition-colors ${opt.value === value ? 'bg-brand-surface text-brand-text font-medium' : 'text-brand-secondary hover:bg-brand-surface hover:text-brand-text'}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
