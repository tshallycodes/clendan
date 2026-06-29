'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { House, CheckSquare, Plugs, Code, Cpu, Gear, SignOut } from '@phosphor-icons/react'
import { useClerk } from '@clerk/nextjs'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { motion } from 'framer-motion'
import { Logo } from '@/components/Logo'

const NAV: { icon: React.ElementType; label: string; href: string; external?: boolean }[] = [
  { icon: House,        label: 'Dashboard',    href: '/dashboard' },
  { icon: CheckSquare, label: 'Approvals',    href: '/approvals' },
  { icon: Plugs,       label: 'Integrations', href: '/dashboard/integrations' },
  { icon: Cpu,         label: 'Tools',        href: '/tools' },
  { icon: Code,        label: 'Developer',    href: '/developer' },
  { icon: Gear,        label: 'Settings',     href: '/settings' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { signOut } = useClerk()

  return (
    <motion.aside
      initial={{ y: -48, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 400, damping: 12, mass: 0.8 }}
      className="hidden lg:flex w-64 shrink-0 bg-brand-surface border border-brand-border rounded-2xl flex-col sticky top-2 h-[calc(100vh-1rem)] mx-3 my-2 overflow-hidden"
      style={{ boxShadow: 'var(--nav-shadow-raised)' }}
    >
      <div className="px-5 py-5 border-b border-brand-border">
        <Logo size="lg" />
      </div>

      <nav className="flex-1 py-4">
        {NAV.map(({ icon: Icon, label, href, external }) => {
          const active = !external && (pathname === href || (href !== '/dashboard' && pathname.startsWith(href)))
          const cls = cn(
            'flex items-center gap-3 px-5 py-2.5 text-xs font-mono transition-colors relative',
            active ? 'text-brand-text bg-brand-elevated' : 'text-brand-muted hover:text-brand-text hover:bg-brand-bg/50',
          )
          return external ? (
            <a key={href} href={href} target="_blank" rel="noopener noreferrer" className={cls}>
              <Icon className="w-4 h-4 shrink-0" />
              <span>{label}</span>
            </a>
          ) : (
            <Link key={href} href={href} className={cls}>
              {active && (
                <motion.span
                  layoutId="sidebar-active"
                  className="absolute left-0 top-1 bottom-1 w-0.5 bg-brand-green rounded-r-full"
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                />
              )}
              <Icon className="w-4 h-4 shrink-0" />
              <span>{label}</span>
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t border-brand-border space-y-2">
        <div className="flex items-center gap-2">
          <Link href="/" className="flex-1 text-xs font-mono text-brand-muted hover:text-brand-text transition-colors flex items-center justify-center gap-2 border border-brand-border px-3 py-2 rounded-sm">
            ← Back to site
          </Link>
          <ThemeToggle />
        </div>
        <button
          type="button"
          onClick={() => signOut({ redirectUrl: '/sign-in' })}
          className="w-full text-xs font-mono text-brand-muted hover:text-[#c5123b] transition-colors flex items-center justify-center gap-2 border border-brand-border px-3 py-2 rounded-sm"
        >
          <SignOut className="w-3 h-3" />
          Sign out
        </button>
      </div>
    </motion.aside>
  )
}
