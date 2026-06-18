'use client'

import { useEffect, useState } from 'react'

const LOG_LINES: { time: string; text: string; color?: string }[] = [
  { time: '09:14:52', text: 'Invoice received: Acme Supplies Ltd £1,240.00', color: '#e8f0e8' },
  { time: '09:14:52', text: 'Extracting data... confidence: 0.97', color: '#a0b8a0' },
  { time: '09:14:53', text: 'Policy check: amount threshold → APPROVAL_REQUIRED', color: '#00a8cc' },
  { time: '09:14:53', text: 'Routing to approval queue...', color: '#a0b8a0' },
  { time: '09:14:58', text: 'Approved by Sarah Chen', color: '#00C853' },
  { time: '09:14:58', text: 'Bill created in QuickBooks — BILL-4421', color: '#00C853' },
]

const CYCLE_DURATION = 9000

export function HeroTerminal() {
  const [cycle, setCycle] = useState(0)

  useEffect(() => {
    const timer = setTimeout(() => setCycle((c) => c + 1), CYCLE_DURATION)
    return () => clearTimeout(timer)
  }, [cycle])

  return (
    // Float wrapper — never remounts, float runs continuously
    <div className="hero-float w-full max-w-2xl mx-auto mt-10">
      {/* key={cycle} remounts only the inner shell to replay log line animations */}
      <div
        key={cycle}
        className="rounded-sm overflow-hidden"
        style={{ background: '#0a0a0a', border: '1px solid #1a2a1a' }}
      >
        <div
          className="flex items-center gap-1.5 px-4 py-2.5 border-b border-brand-border"
          style={{ background: '#111111' }}
        >
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ff4d6d', opacity: 0.7 }} />
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#f5a623', opacity: 0.7 }} />
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#00C853', opacity: 0.7 }} />
          <span className="ml-3 text-xs font-mono text-brand-muted">invoice-tool — execution log</span>
        </div>
        <div className="p-5 flex flex-col gap-2" aria-label="Execution log">
          {LOG_LINES.map((line, i) => (
            <div
              key={i}
              className="flex items-start gap-3 text-xs font-mono"
              style={{
                opacity: 0,
                animation: `terminalFadeIn 0.4s ease-out forwards`,
                animationDelay: `${0.3 + i * 0.55}s`,
              }}
            >
              <span style={{ color: '#4a6a4a', flexShrink: 0 }}>[{line.time}]</span>
              <span style={{ color: line.color ?? '#e8f0e8' }}>{line.text}</span>
            </div>
          ))}
          <div
            className="flex items-center gap-3 text-xs font-mono"
            style={{
              opacity: 0,
              animation: `terminalFadeIn 0.4s ease-out forwards`,
              animationDelay: `${0.3 + LOG_LINES.length * 0.55}s`,
            }}
          >
            <span style={{ color: '#4a6a4a' }}>{'>'}</span>
            <span className="terminal-cursor" style={{ color: '#00C853' }}>█</span>
          </div>
        </div>
      </div>
    </div>
  )
}
