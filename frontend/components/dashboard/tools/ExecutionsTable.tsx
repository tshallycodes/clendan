'use client'

import type { Execution } from './ToolDetail'

const DECISION_BADGE: Record<string, string> = {
  auto_approved:     'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]',
  approval_required: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]',
  blocked:           'bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]',
  failed:            'bg-[rgba(255,77,109,0.06)] text-[#ff4d6d] border border-[rgba(255,77,109,0.15)]',
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
}

interface Props {
  executions: Execution[]
}

export function ExecutionsTable({ executions }: Props) {
  if (executions.length === 0) {
    return (
      <div className="border border-brand-border rounded-sm p-8 text-center">
        <p className="text-xs font-mono text-[#4a6a4a]">No executions yet. Use Run test to trigger this tool.</p>
      </div>
    )
  }

  return (
    <div className="border border-brand-border rounded-sm overflow-hidden">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-brand-border">
            {['Time', 'Decision', 'Confidence', 'Duration', 'Status'].map((h) => (
              <th key={h} className="text-left text-[10px] font-mono text-[#4a6a4a] px-3 py-2 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {executions.map((e) => (
            <tr key={e.id} className="border-b border-brand-border last:border-0 hover:bg-[#1a1a1a] transition-colors">
              <td className="px-3 py-2 text-[#4a6a4a]">{formatDate(e.created_at)}</td>
              <td className="px-3 py-2">
                <span className={`text-[10px] px-2 py-0.5 rounded-sm ${DECISION_BADGE[e.decision] ?? 'text-brand-muted border border-brand-border'}`}>
                  {e.decision.replace(/_/g, ' ')}
                </span>
              </td>
              <td className="px-3 py-2 text-brand-muted">
                {e.confidence !== null ? `${(e.confidence * 100).toFixed(1)}%` : '—'}
              </td>
              <td className="px-3 py-2 text-brand-muted">{formatDuration(e.duration_ms)}</td>
              <td className="px-3 py-2 text-brand-muted">{e.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
