'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Props {
  documentId: string
  filename: string | null
  onClose: () => void
}

function SummaryBody({ summary }: { summary: string }) {
  const lines = summary.split('\n')
  return (
    <div className="space-y-0.5">
      {lines.map((line, i) => {
        if (line.startsWith('## ')) {
          return (
            <p
              key={i}
              className="text-xs font-mono font-semibold text-brand-text uppercase tracking-widest mt-4 mb-1"
            >
              {line.replace(/^## /, '')}
            </p>
          )
        }
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} className="flex gap-2">
              <span className="text-[10px] font-mono text-brand-muted shrink-0 mt-0.5">→</span>
              <p className="text-xs font-mono text-brand-secondary leading-relaxed">
                {line.replace(/^[-•] /, '')}
              </p>
            </div>
          )
        }
        if (line.trim() === '') return null
        return (
          <p key={i} className="text-xs font-mono text-brand-secondary leading-relaxed">
            {line}
          </p>
        )
      })}
    </div>
  )
}

export function ContractSummaryDrawer({ documentId, filename, onClose }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [summary, setSummary] = useState<string | null>(null)
  const [loadingState, setLoadingState] = useState<'loading' | 'error' | 'done'>('loading')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function fetchSummary() {
    setLoadingState('loading')
    setErrorMsg(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/documents/${documentId}/summarise`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const json = await res.json().catch(() => ({}))
      if (!res.ok) {
        const msg = (json as { detail?: string }).detail ?? 'Failed to summarise document'
        setErrorMsg(msg)
        setLoadingState('error')
        return
      }
      setSummary((json as { data?: { summary?: string }; summary?: string }).data?.summary ?? (json as { summary?: string }).summary ?? '')
      setLoadingState('done')
    } catch {
      setErrorMsg('Network error — could not reach the server')
      setLoadingState('error')
      toast('Failed to load contract summary', 'error')
    }
  }

  useEffect(() => {
    fetchSummary()
  }, [documentId])

  return (
    <AnimatePresence>
      <>
        {/* Backdrop */}
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />

        {/* Drawer */}
        <motion.div
          key="drawer"
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="fixed inset-y-0 right-0 w-[480px] bg-brand-surface border-l border-brand-border z-50 flex flex-col"
        >
          {/* Header */}
          <div className="flex items-start justify-between px-5 py-4 border-b border-brand-border shrink-0">
            <div className="min-w-0 pr-4">
              <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">
                Contract Summary
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

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {loadingState === 'loading' && (
              <div className="flex flex-col items-center justify-center gap-3 mt-16">
                <div className="w-5 h-5 border-2 border-[#00C853] border-t-transparent rounded-full animate-spin" />
                <p className="text-xs font-mono text-brand-muted">Clen is reading the contract…</p>
              </div>
            )}

            {loadingState === 'error' && (
              <div className="mt-6 space-y-3">
                <p className="text-xs font-mono text-[#ff4d6d]">{errorMsg}</p>
                <button
                  type="button"
                  onClick={fetchSummary}
                  className="text-[10px] font-mono px-3 py-1.5 rounded-sm border border-brand-border text-brand-text hover:bg-brand-elevated transition-colors"
                >
                  Retry
                </button>
              </div>
            )}

            {loadingState === 'done' && summary !== null && (
              <SummaryBody summary={summary} />
            )}
          </div>
        </motion.div>
      </>
    </AnimatePresence>
  )
}
