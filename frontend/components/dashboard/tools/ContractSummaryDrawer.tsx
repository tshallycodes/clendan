'use client'

import { useRef, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Message {
  question: string
  answer: string
}

interface Props {
  documentId: string
  filename: string | null
  onClose: () => void
}

export function AskClenDrawer({ documentId, filename, onClose }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  async function handleAsk() {
    const q = question.trim()
    if (!q || loading) return
    setLoading(true)
    setQuestion('')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/documents/${documentId}/ask`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      const json = await res.json().catch(() => ({}))
      if (!res.ok) {
        toast((json as { detail?: string }).detail ?? 'Failed to get answer', 'error')
        setQuestion(q)
        return
      }
      const answer = (json as { data?: { answer?: string } }).data?.answer ?? ''
      setMessages(prev => [...prev, { question: q, answer }])
      setTimeout(() => inputRef.current?.focus(), 50)
    } catch {
      toast('Network error — could not reach the server', 'error')
      setQuestion(q)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAsk()
    }
  }

  return (
    <AnimatePresence>
      <>
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />

        <motion.div
          key="drawer"
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="fixed inset-y-0 right-0 w-[480px] bg-brand-surface border-l border-brand-border z-50 flex flex-col"
        >
          <div className="flex items-start justify-between px-5 py-4 border-b border-brand-border shrink-0">
            <div className="min-w-0 pr-4">
              <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">
                Ask Clen
              </p>
              <p className="text-sm font-mono text-brand-text truncate">
                {filename ?? 'Untitled document'}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 text-brand-muted hover:text-brand-text transition-colors text-sm font-mono mt-0.5"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
            {messages.length === 0 && !loading && (
              <p className="text-xs font-mono text-brand-muted mt-4">
                Ask Clen anything about this document — risks, clauses, obligations, summaries.
              </p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className="space-y-2">
                <div className="flex gap-2">
                  <span className="text-[10px] font-mono text-brand-muted shrink-0 mt-0.5">You</span>
                  <p className="text-xs font-mono text-brand-secondary">{msg.question}</p>
                </div>
                <div className="flex gap-2">
                  <span className="text-[10px] font-mono text-[#00C853] shrink-0 mt-0.5">Clen</span>
                  <p className="text-xs font-mono text-brand-text leading-relaxed whitespace-pre-wrap">{msg.answer}</p>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-2 items-center">
                <span className="text-[10px] font-mono text-[#00C853] shrink-0">Clen</span>
                <div className="flex gap-1">
                  {[0, 1, 2].map(i => (
                    <div key={i} className="w-1.5 h-1.5 rounded-full bg-[#00C853] animate-bounce" style={{ animationDelay: `${i * 120}ms` }} />
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="px-5 py-4 border-t border-brand-border shrink-0">
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question… (Enter to send)"
                rows={2}
                className="flex-1 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono resize-none outline-none transition-colors"
              />
              <button
                type="button"
                onClick={handleAsk}
                disabled={!question.trim() || loading}
                className="shrink-0 text-[10px] font-mono px-4 py-2 rounded-sm bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? '…' : 'Ask'}
              </button>
            </div>
            <p className="text-[10px] font-mono text-brand-muted mt-1.5">Shift+Enter for new line</p>
          </div>
        </motion.div>
      </>
    </AnimatePresence>
  )
}
