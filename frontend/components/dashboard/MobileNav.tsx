'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { House, CheckSquare, Plugs, Code, Cpu, Gear, SignOut, List, X } from '@phosphor-icons/react'
import { useClerk } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Logo } from '@/components/Logo'

const NAV: { icon: React.ElementType; label: string; href: string; external?: boolean }[] = [
  { icon: House,        label: 'Dashboard',    href: '/dashboard' },
  { icon: CheckSquare, label: 'Approvals',    href: '/approvals' },
  { icon: Plugs,       label: 'Integrations', href: '/dashboard/integrations' },
  { icon: Cpu,         label: 'Tools',        href: '/tools' },
  { icon: Code,        label: 'Developer',    href: '/developer' },
  { icon: Gear,        label: 'Settings',     href: '/settings' },
]

export function MobileNav() {
  const [open, setOpen] = useState(false)
  const pathname = usePathname()
  const { signOut } = useClerk()

  return (
    <>
      {/* Fixed top bar — mobile/tablet only */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-4 py-4 bg-brand-surface border-b border-brand-border">
        <Logo size="sm" />
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="text-brand-muted hover:text-brand-text transition-colors p-1"
          aria-label="Open navigation"
        >
          <List className="w-5 h-5" />
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/60 lg:hidden"
              onClick={() => setOpen(false)}
            />

            {/* Drawer */}
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
              className="fixed left-0 top-0 bottom-0 z-50 w-56 bg-brand-surface border-r border-brand-border flex flex-col lg:hidden"
            >
              <div className="flex items-center justify-between px-4 py-4 border-b border-brand-border">
                <Logo size="sm" />
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="text-brand-muted hover:text-brand-text transition-colors p-1"
                  aria-label="Close navigation"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <nav className="flex-1 py-4 overflow-y-auto">
                {NAV.map(({ icon: Icon, label, href, external }) => {
                  const active = !external && (pathname === href || (href !== '/dashboard' && pathname.startsWith(href)))
                  const cls = cn(
                    'flex items-center gap-3 px-5 py-2.5 text-xs font-body transition-colors relative',
                    active ? 'text-brand-text bg-brand-elevated' : 'text-brand-muted hover:text-brand-text hover:bg-brand-elevated',
                  )
                  return external ? (
                    <a key={href} href={href} target="_blank" rel="noopener noreferrer" onClick={() => setOpen(false)} className={cls}>
                      <Icon className="w-4 h-4 shrink-0" />
                      <span>{label}</span>
                    </a>
                  ) : (
                    <Link key={href} href={href} onClick={() => setOpen(false)} className={cls}>
                      {active && <span className="absolute left-0 top-1 bottom-1 w-0.5 bg-brand-green rounded-r-full" />}
                      <Icon className="w-4 h-4 shrink-0" />
                      <span>{label}</span>
                    </Link>
                  )
                })}
              </nav>

              <div className="p-4 border-t border-brand-border space-y-2">
                <div className="flex items-center gap-2">
                  <Link
                    href="/"
                    onClick={() => setOpen(false)}
                    className="flex-1 text-xs font-body text-brand-muted hover:text-brand-text transition-colors flex items-center justify-center gap-2 border border-brand-border px-3 py-2 rounded-sm"
                  >
                    ← Back to site
                  </Link>
                  <ThemeToggle />
                </div>
                <button
                  type="button"
                  onClick={() => signOut({ redirectUrl: '/sign-in' })}
                  className="w-full text-xs font-body text-brand-muted hover:text-[#ff4d6d] transition-colors flex items-center justify-center gap-2 border border-brand-border px-3 py-2 rounded-sm"
                >
                  <SignOut className="w-3 h-3" />
                  Sign out
                </button>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
