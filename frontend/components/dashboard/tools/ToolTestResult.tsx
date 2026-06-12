'use client'

import { useEffect } from 'react'

export interface TestResult {
  decision: string
  confidence: number | null
  error?: string
}

const DECISION_STYLES: Record<string, { label: string; className: string }> = {
  auto_approved:      { label: 'Auto Approved',      className: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]' },
  approval_required:  { label: 'Approval Required',  className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
  blocked:            { label: 'Blocked',             className: 'bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]' },
  failed:             { label: 'Failed',              className: 'bg-[rgba(255,77,109,0.06)] text-[#ff4d6d] border border-[rgba(255,77,109,0.15)]' },
  routed:             { label: 'Queued',              className: 'bg-[#111111] text-[#a0b8a0] border border-[#1a2a1a]' },
  queued:             { label: 'Queued',              className: 'bg-[#111111] text-[#a0b8a0] border border-[#1a2a1a]' },
}

const AUTO_DISMISS_MS = 8000

interface Props {
  result: TestResult
  onDismiss: () => void
}

export function ToolTestResult({ result, onDismiss }: Props) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, AUTO_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [onDismiss])

  if (result.error) {
    return (
      <div className="flex items-center justify-between mt-3 px-3 py-2 bg-[rgba(255,77,109,0.06)] border border-[rgba(255,77,109,0.2)] rounded-sm">
        <span className="text-[11px] font-mono text-[#ff4d6d]">{result.error}</span>
        <button type="button" onClick={onDismiss} className="text-[#ff4d6d] text-[10px] font-mono ml-3 hover:opacity-70 transition-opacity">Ã—</button>
      </div>
    )
  }

  const style = DECISION_STYLES[result.decision] ?? { label: result.decision, className: 'bg-[#111111] text-[#a0b8a0] border border-[#1a2a1a]' }
  const isQueued = result.decision === 'routed' || result.decision === 'queued'

  return (
    <div className="flex items-center justify-between mt-3 px-3 py-2 bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm">
      <div className="flex items-center gap-3">
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${style.className}`}>{style.label}</span>
        {result.confidence !== null && !isQueued && (
          <span className="text-[11px] font-mono text-[#a0b8a0]">
            {(result.confidence * 100).toFixed(1)}% confidence
          </span>
        )}
        {isQueued && (
          <span className="text-[11px] font-mono text-[#4a6a4a]">
            Execution queued â€” check Executions page for results
          </span>
        )}
      </div>
      <button type="button" onClick={onDismiss} className="text-[#4a6a4a] text-[10px] font-mono ml-3 hover:text-[#a0b8a0] transition-colors">Ã—</button>
    </div>
  )
}
