'use client'

import { CaretUp, CaretDown } from '@phosphor-icons/react'

interface NumberInputProps {
  value: number
  min?: number
  max?: number
  step?: number
  onChange: (v: number) => void
  className?: string
}

export function NumberInput({ value, min, max, step = 1, onChange, className }: NumberInputProps) {
  function clamp(n: number) {
    let v = n
    if (min !== undefined) v = Math.max(min, v)
    if (max !== undefined) v = Math.min(max, v)
    return v
  }

  function round(n: number) {
    if (step < 1) return parseFloat(n.toFixed(10))
    return Math.round(n)
  }

  const increment = () => onChange(clamp(round(value + step)))
  const decrement = () => onChange(clamp(round(value - step)))

  return (
    <div className={`flex bg-brand-bg border border-brand-border rounded-sm overflow-hidden focus-within:border-[#00C853] transition-colors ${className ?? ''}`}>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={e => {
          const raw = step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value, 10)
          if (!isNaN(raw)) onChange(clamp(raw))
        }}
        className="flex-1 min-w-0 bg-transparent px-3 py-2 text-xs font-body text-brand-text outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
      />
      <div className="flex flex-col border-l border-brand-border shrink-0">
        <button
          type="button"
          onClick={increment}
          className="flex-1 w-7 flex items-center justify-center text-brand-muted hover:text-brand-text hover:bg-brand-elevated border-b border-brand-border transition-colors"
        >
          <CaretUp size={10} />
        </button>
        <button
          type="button"
          onClick={decrement}
          className="flex-1 w-7 flex items-center justify-center text-brand-muted hover:text-brand-text hover:bg-brand-elevated transition-colors"
        >
          <CaretDown size={10} />
        </button>
      </div>
    </div>
  )
}
