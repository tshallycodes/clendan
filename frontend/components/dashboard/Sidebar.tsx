'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, CheckSquare, List, Plug, BarChart2, Code2, Cpu, Settings, LogOut } from 'lucide-react'
import { useClerk } from '@clerk/nextjs'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'

const NAV = [
  { icon: Home,        label: 'Dashboard',    href: '/dashboard' },
  { icon: CheckSquare, label: 'Approvals',    href: '/dashboard/approvals' },
  { icon: BarChart2,   label: 'Executions',   href: '/dashboard/executions' },
  { icon: List,        label: 'Audit Trail',  href: '/dashboard/audit' },
  { icon: Plug,        label: 'Integrations', href: '/dashboard/integrations' },
  { icon: Cpu,         label: 'Workers',      href: '/dashboard/workers' },
  { icon: Settings,    label: 'Settings',     href: '/dashboard/settings' },
  { icon: Code2,       label: 'Developer API', href: '/dashboard/api' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { signOut } = useClerk()

  return (
    <aside className="w-56 shrink-0 bg-brand-surface border-r border-brand-border flex flex-col h-screen sticky top-0">
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-brand-border">
        <span className="w-6 h-6 rounded-sm border border-brand-green flex items-center justify-center font-heading font-bold text-brand-green text-xs">
          C
        </span>
        <span className="font-heading font-bold text-brand-text text-xs tracking-[0.15em] uppercase">
          Clendan
        </span>
      </div>

      <nav className="flex-1 py-4">
        {NAV.map(({ icon: Icon, label, href }) => {
          const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-5 py-2.5 text-xs font-mono transition-colors relative',
                active ? 'text-brand-text bg-brand-elevated' : 'text-brand-muted hover:text-brand-text hover:bg-brand-elevated/50',
              )}
            >
              {active && <span className="absolute left-0 top-1 bottom-1 w-0.5 bg-brand-green rounded-r-full" />}
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
