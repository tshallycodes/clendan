'use client'

import { useEffect, useRef } from 'react'
import { useClen } from '@/components/clen/useClen'
import { ClenMessage } from '@/components/clen/ClenMessage'
import { ClenInput } from '@/components/clen/ClenInput'

// Operator starters — reads that answer "where do I stand" and actions that do work.
const SUGGESTIONS = ["What's my cash position?", "Who's overdue?", 'Run Spend Control', 'What VAT do I owe?']

// The agent, inline and front-and-centre on the dashboard home (not a corner pill). Reuses the
// same useClen conversation state as the launcher, so history persists across both.
export function InlineAgent() {
  const { messages, isLoading, sendMessage } = useClen('account')
  const threadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isLoading])

  const empty = messages.length === 0

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden flex flex-col">
      <div className="px-5 py-4 border-b border-brand-border">
        <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Ask Clendan</p>
        <h2 className="font-heading font-bold text-xl text-brand-text mt-1">What do you need done?</h2>
        <p className="text-xs font-body text-brand-muted mt-1 max-w-xl leading-relaxed">
          Ask in plain language — Clendan reads your connected books and does the work in them, with your sign-off on anything that changes.
        </p>
      </div>

      <div ref={threadRef} className="flex-1 overflow-y-auto px-5 py-4 min-h-[180px] max-h-[440px]">
        {empty ? (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => sendMessage(s)}
                className="text-[11px] font-body text-brand-secondary border border-brand-border rounded-full px-3 py-1 hover:bg-brand-elevated hover:text-brand-text transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        ) : (
          <>
            {messages.map((m) => <ClenMessage key={m.id} message={m} />)}
            {isLoading && messages[messages.length - 1]?.content === '' && (
              <div className="text-[11px] font-body text-brand-muted">Clen is thinking…</div>
            )}
          </>
        )}
      </div>

      <ClenInput onSend={sendMessage} disabled={isLoading} />
    </div>
  )
}
