'use client'

import Link from 'next/link'
import { Cpu, Receipt, CheckSquare } from '@phosphor-icons/react'

const ACTIONS = [
  {
    href: '/tools',
    Icon: Cpu,
    title: 'Deploy Tool',
    desc: 'Add a new AI agent to your workflow.',
  },
  {
    href: '/transactions',
    Icon: Receipt,
    title: 'View Transactions',
    desc: 'Browse and categorise synced bank data.',
  },
  {
    href: '/approvals',
    Icon: CheckSquare,
    title: 'Review Approvals',
    desc: 'Action pending decisions from your agents.',
  },
]

export function QuickActions() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {ACTIONS.map(({ href, Icon, title, desc }) => (
        <Link
          key={href}
          href={href}
          className="bg-brand-surface border border-brand-border rounded-sm p-4 flex items-start gap-3 hover:bg-brand-elevated transition-colors group"
        >
          <Icon className="w-4 h-4 text-brand-muted group-hover:text-brand-text transition-colors mt-0.5 shrink-0" />
          <div>
            <p className="text-xs font-body font-medium text-brand-text">{title}</p>
            <p className="text-[11px] font-body text-brand-muted mt-0.5">{desc}</p>
          </div>
        </Link>
      ))}
    </div>
  )
}
