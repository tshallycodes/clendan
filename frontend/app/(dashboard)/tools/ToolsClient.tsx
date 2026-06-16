'use client'

import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { TOOLS } from './tools-data'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

interface Props {
  deployedTools: Tool[]
}

function StatusBadge({ tool }: { tool: Tool | undefined }) {
  if (!tool) return <span className="text-[10px] font-mono text-brand-muted">Not deployed</span>
  const active = tool.status === 'active'
  return (
    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${
      active
        ? 'bg-[rgba(0,200,83,0.08)] text-brand-green border border-[rgba(0,200,83,0.2)]'
        : 'bg-brand-elevated text-brand-muted border border-brand-border'
    }`}>
      {active ? 'Active' : 'Inactive'}
    </span>
  )
}

export function ToolsClient({ deployedTools }: Props) {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Tools</h1>
        <p className="text-[10px] font-mono text-brand-muted mt-1 uppercase tracking-widest">
          AI financial tools
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {TOOLS.map((tool) => {
          const deployed = deployedTools.find((w) => w.type === tool.type)
          return (
            <Link
              key={tool.slug}
              href={`/tools/${tool.slug}`}
              className="group bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3 hover:bg-brand-elevated transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-mono font-medium text-brand-text group-hover:text-brand-green transition-colors">
                  {tool.name}
                </p>
                <StatusBadge tool={deployed} />
              </div>
              <p className="text-[11px] font-mono text-brand-muted leading-relaxed flex-1">{tool.desc}</p>
              <div className="flex items-center gap-1 text-[10px] font-mono text-brand-muted group-hover:text-brand-secondary transition-colors">
                Open <ArrowRight className="w-3 h-3" />
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
