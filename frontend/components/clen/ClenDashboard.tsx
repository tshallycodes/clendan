'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { MessageCircle } from 'lucide-react'
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
          'flex items-center gap-1.5 text-[10px] font-mono px-3 py-1.5 border rounded-sm transition-colors',
          isOpen
            ? 'border-brand-green/30 bg-brand-green/10 text-brand-green'
            : 'border-brand-border text-brand-muted hover:text-brand-text hover:bg-brand-elevated/50',
        )}
      >
        <MessageCircle className="w-3 h-3 shrink-0" />
        Ask Clen
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
