'use client'

import Link from 'next/link'
import { ToolTestResult } from './ToolTestResult'
import { ExecutionsTable } from './ExecutionsTable'
import { useRunTest } from './useRunTest'
import { formatType } from './ToolCard'
import type { Tool } from './ToolCard'

export interface Execution {
  id: string
  tool_id: string
  tool_type: string
  decision: string
  confidence: number | null
  status: string
  duration_ms: number | null
  created_at: string
}

interface Props {
  tool: Tool
  executions: Execution[]
}

export function ToolDetail({ tool, executions }: Props) {
  const { run, running, result, dismiss } = useRunTest(tool.id, tool.type)

  const isActive      = tool.status === 'active'
  const configEntries = Object.entries(tool.config_json ?? {})

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <Link href="/tools" className="text-[12px] font-body text-brand-muted hover:text-[#a0b8a0] transition-colors">
            &larr; Tools
          </Link>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="font-heading font-bold text-2xl text-[#e8f0e8]">{formatType(tool.type)}</h1>
            <span className="text-[11px] font-body text-brand-muted">v{tool.version}</span>
            <div className="flex items-center gap-1.5">
              {isActive ? (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-60" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00C853]" />
                </span>
              ) : (
                <span className="h-2 w-2 rounded-full bg-[#4a6a4a]" />
              )}
              <span className={`text-xs font-body ${isActive ? 'text-[#00C853]' : 'text-brand-muted'}`}>
                {isActive ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={running}
          className="text-xs font-body border border-brand-border text-[#e8f0e8] hover:bg-[#1a1a1a] rounded-sm px-3 py-1.5 transition-colors disabled:opacity-50 shrink-0"
        >
          {running ? 'Running…' : 'Run test'}
        </button>
      </div>

      {result && <ToolTestResult result={result} onDismiss={dismiss} />}

      {configEntries.length > 0 && (
        <section>
          <h2 className="font-heading font-semibold text-sm text-[#e8f0e8] mb-3">Configuration</h2>
          <div className="bg-[#111111] border border-brand-border rounded-sm p-4 space-y-2">
            {configEntries.map(([k, v]) => (
              <div key={k} className="flex gap-4 text-xs font-body">
                <span className="text-brand-muted min-w-[140px] shrink-0">{k}</span>
                <span className="text-[#e8f0e8] break-all">{String(v)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="font-heading font-semibold text-sm text-[#e8f0e8] mb-3">Recent Executions</h2>
        <ExecutionsTable executions={executions} />
      </section>
    </div>
  )
}
