'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { ChatCircle } from '@phosphor-icons/react'
import { ClenPanel } from './ClenPanel'
import { cn } from '@/lib/utils'

export function ClenDashboard() {
  const [isOpen, setIsOpen] = useState(false)
  const pathname = usePathname()

  return (
    <>
      <button
        onClick={() => setIsOpen(p => !p)}
        className={cn(
          'relative flex items-center gap-2 text-[11px] font-body px-3 py-1.5 border rounded-sm transition-all duration-200 active:scale-95',
          isOpen
            ? 'border-brand-green/40 bg-brand-green/10 text-brand-green shadow-[0_0_12px_rgba(0,200,83,0.15)]'
            : 'border-brand-green/25 bg-brand-green/5 text-brand-text hover:border-brand-green/50 hover:bg-brand-green/10 hover:text-brand-green shadow-[0_0_8px_rgba(0,200,83,0.08)] hover:shadow-[0_0_14px_rgba(0,200,83,0.2)]',
        )}
      >
        <span className={cn(
          'relative flex items-center justify-center',
          !isOpen && 'animate-[clen-pulse_2.4s_ease-in-out_infinite]',
        )}>
          <ChatCircle className={cn(
            'w-3.5 h-3.5 shrink-0 transition-colors',
            isOpen ? 'text-brand-green' : 'text-brand-green',
          )} />
        </span>
        <span>Ask Clen</span>
        {!isOpen && (
          <span className="w-1.5 h-1.5 rounded-full bg-brand-green animate-[clen-dot_2.4s_ease-in-out_infinite]" />
        )}
      </button>

      <ClenPanel
        mode="account"
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        position="sidebar"
        pathname={pathname}
      />
    </>
  )
}
