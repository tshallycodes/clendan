'use client'

import { useState } from 'react'

export function WarningBanner() {
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div className="w-full bg-[#f5a623] text-black text-[12px] font-body font-medium text-center py-1.5 px-4 tracking-wide z-[9999] relative flex items-center justify-center">
      <span>This platform is under active development - not intended for public use.</span>
      <button
        onClick={() => setDismissed(true)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-black/60 hover:text-black transition-colors leading-none"
        aria-label="Dismiss warning"
      >
        ✕
      </button>
    </div>
  )
}
