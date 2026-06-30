'use client'

import { useState } from 'react'

export function PricingToggle() {
  const [annual, setAnnual] = useState(false)

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => setAnnual(false)}
        className={`font-body text-[13px] transition-colors ${
          !annual ? 'text-brand-text' : 'text-brand-muted hover:text-brand-secondary'
        }`}
      >
        Monthly
      </button>

      <button
        onClick={() => setAnnual(!annual)}
        aria-label="Toggle billing period"
        className={`relative w-11 h-6 rounded-full border transition-colors ${
          annual
            ? 'bg-brand-green border-brand-green'
            : 'bg-brand-surface border-brand-border'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 bg-black rounded-full transition-transform duration-200 ${
            annual ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>

      <button
        onClick={() => setAnnual(true)}
        className={`font-body text-[13px] flex items-center gap-2 transition-colors ${
          annual ? 'text-brand-text' : 'text-brand-muted hover:text-brand-secondary'
        }`}
      >
        Annual
        <span className="bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)] text-brand-green font-body text-[11px] uppercase tracking-wider px-2 py-0.5 rounded-sm">
          2 months free
        </span>
      </button>
    </div>
  )
}
