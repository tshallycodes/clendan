'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight } from '@phosphor-icons/react'
import { askClen } from '@/components/clen/clen-launcher'

// Operator-framed starters: reads that answer "where do I stand" and actions that do work.
const SUGGESTIONS = [
  "What's my cash position?",
  "Who's overdue?",
  'Run Spend Control',
  'What VAT do I owe?',
]

export function AskClendanHero() {
  const [text, setText] = useState('')

  function submit(q: string) {
    const v = q.trim()
    if (v) askClen(v)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="bg-brand-surface border border-brand-border rounded-sm p-5 lg:p-6"
    >
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Ask Clendan</p>
      <h2 className="font-heading font-bold text-xl text-brand-text mt-1.5">What do you need done?</h2>
      <p className="text-xs font-body text-brand-muted mt-1 max-w-xl leading-relaxed">
        Ask in plain language — Clendan reads your connected books and does the work in them, with your sign-off on anything that changes.
      </p>

      <form onSubmit={(e) => { e.preventDefault(); submit(text) }} className="mt-4 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Chase everyone who's overdue, or run this week's bills"
          className="flex-1 min-w-0 bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-body text-brand-text placeholder:text-brand-muted outline-none transition-colors"
        />
        <button
          type="submit"
          className="shrink-0 flex items-center gap-1.5 bg-brand-green text-black text-xs font-body font-medium rounded-sm px-3.5 py-2 hover:bg-[#00a844] active:scale-[0.97] transition-all"
        >
          Ask <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => submit(s)}
            className="text-[11px] font-body text-brand-secondary border border-brand-border rounded-full px-3 py-1 hover:bg-brand-elevated hover:text-brand-text transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </motion.div>
  )
}
