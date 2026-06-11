'use client'

import { motion } from 'framer-motion'
import type { ClenMessage as ClenMessageType } from './useClen'

interface Props {
  message: ClenMessageType
}

export function ClenMessage({ message }: Props) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.15 }}
        className="group flex justify-end mb-3"
      >
        <div className="relative max-w-[80%]">
          <div className="bg-brand-elevated rounded-sm px-3 py-2 text-xs font-mono text-brand-text leading-relaxed">
            {message.content}
          </div>
          <span className="absolute -bottom-4 right-0 text-[11px] font-mono text-brand-muted opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="group flex gap-2 mb-3"
    >
      <span
        className="text-brand-green font-mono text-xs font-bold mt-0.5 shrink-0 leading-relaxed"
        aria-hidden="true"
      >
        C
      </span>
      <div className="flex-1 min-w-0">
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.toolCalls.map((tc, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-[10px] font-mono text-brand-muted bg-brand-surface border border-brand-border-subtle rounded-sm px-2 py-1"
              >
                <span className="text-brand-warning">◌</span>
                <span>Checking your data</span>
                <span className="text-brand-border-subtle">·</span>
                <span className="truncate">{tc.tool}</span>
                {tc.result && <span className="ml-auto text-brand-green">✓</span>}
              </div>
            ))}
          </div>
        )}
        {message.content && (
          <div className="text-xs font-mono text-brand-text leading-relaxed whitespace-pre-wrap">
            {message.content}
          </div>
        )}
        <span className="block mt-1 text-[11px] font-mono text-brand-muted opacity-0 group-hover:opacity-100 transition-opacity">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </motion.div>
  )
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
