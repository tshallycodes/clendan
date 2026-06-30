'use client'

import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { ClenMode } from './useClen'
import { useClen } from './useClen'
import { ClenMessage } from './ClenMessage'
import { ClenInput } from './ClenInput'
import { ClenSuggestions } from './ClenSuggestions'
import { ClenContextBar } from './ClenContextBar'

export interface ClenPanelProps {
  mode: ClenMode
  isOpen: boolean
  onClose: () => void
  position: 'floating' | 'sidebar'
  pathname?: string
}

const WELCOME = `Hi, I'm Clen — Clendan's assistant.\n\nAsk me anything about how Clendan works,\nour integrations, API tools, or pricing.`

const floatingVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1 },
}

const sidebarVariants = {
  hidden: { opacity: 0, x: 40 },
  visible: { opacity: 1, x: 0 },
}

export function ClenPanel({ mode, isOpen, onClose, position, pathname = '/dashboard' }: ClenPanelProps) {
  const { messages, isLoading, sendMessage, clearConversation, error } = useClen(mode)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const variants = position === 'floating' ? floatingVariants : sidebarVariants

  const containerClass =
    position === 'floating'
      ? 'fixed bottom-[80px] right-6 w-[380px] h-[560px] z-50'
      : 'fixed right-0 top-0 w-[400px] h-screen z-50'

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="clen-panel"
          variants={variants}
          initial="hidden"
          animate="visible"
          exit="hidden"
          transition={{ duration: 0.2, ease: 'easeOut' }}
          className={`${containerClass} flex flex-col bg-brand-bg border border-brand-border rounded-sm overflow-hidden shadow-2xl`}
        >
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-brand-border shrink-0">
            <span className="text-[#00C853] font-mono font-bold text-sm leading-none">C</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-brand-text" style={{ fontFamily: 'var(--font-heading, sans-serif)' }}>
                  Clen
                </span>
                {mode === 'account' && (
                  <span className="flex items-center gap-1 text-[10px] font-mono text-brand-muted">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#00C853] inline-block" />
                    Connected to your account
                  </span>
                )}
              </div>
              <p className="text-[11px] font-mono text-brand-muted">Clendan Assistant</p>
            </div>
            <button
              onClick={onClose}
              aria-label="Close assistant"
              className="w-6 h-6 flex items-center justify-center text-brand-muted hover:text-brand-text transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          {/* Context bar (account mode only) */}
          {mode === 'account' && <ClenContextBar pathname={pathname} />}

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 pt-4 min-h-0">
            {messages.length === 0 && (
              <div className="mb-4 text-xs font-mono text-brand-secondary leading-relaxed whitespace-pre-line">
                {WELCOME}
              </div>
            )}
            {messages.map(msg => (
              <ClenMessage key={msg.id} message={msg} />
            ))}
            {isLoading && messages[messages.length - 1]?.content === '' && (
              <LoadingDots />
            )}
            {error && (
              <p className="text-[11px] font-mono text-brand-danger mb-3">{error}</p>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Suggestions */}
          {messages.length === 0 && (
            <ClenSuggestions onSelect={text => sendMessage(text)} />
          )}

          {/* Input */}
          <ClenInput onSend={sendMessage} disabled={isLoading} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function LoadingDots() {
  return (
    <div className="flex gap-2 items-center mb-3 pl-5">
      {[0, 1, 2].map(i => (
        <motion.span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-brand-muted"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </div>
  )
}
