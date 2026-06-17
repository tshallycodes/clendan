'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, CheckSquare, Plug, Code2, Cpu, Settings, LogOut, Receipt } from 'lucide-react'
import { useClerk } from '@clerk/nextjs'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { motion } from 'framer-motion'
import { Logo } from '@/components/Logo'

const NAV: { icon: React.ElementType; label: string; href: string; external?: boolean }[] = [
  { icon: Home,        label: 'Dashboard',    href: '/dashboard' },
  { icon: CheckSquare, label: 'Approvals',    href: '/approvals' },
  { icon: Receipt,     label: 'Transactions', href: '/transactions' },
  { icon: Plug,        label: 'Integrations', href: '/dashboard/integrations' },
  { icon: Cpu,         label: 'Tools',        href: '/tools' },
  { icon: Code2,       label: 'Developer',    href: '/developer' },
  { icon: Settings,    label: 'Settings',     href: '/settings' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { signOut } = useClerk()

  return (
    <aside className="hidden lg:flex w-56 shrink-0 bg-brand-surface border border-brand-border rounded-2xl shadow-lg flex-col sticky top-3 h-[calc(100vh-24px)] m-3 overflow-hidden">
      <div className="px-4 py-4 border-b border-brand-border">
        <Logo size="sm" />
      </div>

      <nav className="flex-1 py-4">
        {NAV.map(({ icon: Icon, label, href, external }) => {
          const active = !external && (pathname === href || (href !== '/dashboard' && pathname.startsWith(href)))
          const cls = cn(
            'flex items-center gap-3 px-5 py-2.5 text-xs font-mono transition-colors relative',
            active ? 'text-brand-text bg-brand-elevated' : 'text-brand-muted hover:text-brand-text hover:bg-brand-elevated/50',
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
          className="w-full text-xs font-mono text-brand-muted hover:text-[#ff4d6d] transition-colors flex items-center justify-center gap-2 border border-brand-border px-3 py-2 rounded-sm"
        >
          <LogOut className="w-3 h-3" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
