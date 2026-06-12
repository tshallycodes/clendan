'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import Link from 'next/link'
import { CheckCircle } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import type { Tool } from './ToolCard'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function formatType(type: string): string {
  return type.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') + ' Tool'
}

export interface RunDrawerProps {
  tool: Tool
  onClose: () => void
  onQueued: (executionId: string) => void
}

const inputClass = 'w-full bg-[#0a0a0a] border border-[#1a2a1a] focus:border-[#00C853] text-[#e8f0e8] rounded-sm px-3 py-2 text-xs font-mono outline-none transition-colors resize-none'
const labelClass = 'text-[10px] font-mono text-[#6e8c6e] uppercase tracking-widest'

export function RunDrawer({ tool, onClose, onQueued }: RunDrawerProps) {
  const { getToken } = useAuth()
  const [payloadText, setPayloadText]   = useState('{}')
  const [submitting, setSubmitting]     = useState(false)
  const [error, setError]               = useState<string | null>(null)
  const [payloadError, setPayloadError] = useState<string | null>(null)
  const [queuedId, setQueuedId]         = useState<string | null>(null)

  async function handleSubmit() {
    setPayloadError(null)
    setError(null)

    let parsedPayload: Record<string, unknown>
    try {
      parsedPayload = JSON.parse(payloadText)
    } catch {
      setPayloadError('Invalid JSON — check your payload syntax.')
      return
    }

    setSubmitting(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/agents/${tool.id}/trigger`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Idempotency-Key': crypto.randomUUID(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ payload: parsedPayload }),
      })

      const json = await res.json().catch(() => ({})) as { data?: { execution_id?: string }; error?: string }

      if (!res.ok) {
        setError(json.error ?? 'Failed to trigger execution.')
        return
      }

      const execId = json.data?.execution_id
      if (!execId) {
        setError('Execution queued but no ID returned.')
        return
      }

      setQueuedId(execId)
      onQueued(execId)
    } catch {
      setError('Unable to connect to server.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 bg-[rgba(0,0,0,0.7)] z-40 flex items-end sm:items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        onClick={onClose}
      >
        <motion.div
          className="w-full max-w-md bg-[#111111] border border-[#1a2a1a] rounded-sm overflow-hidden"
          initial={{ y: 32, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 32, opacity: 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#1a2a1a]">
            <h2 className="font-heading font-semibold text-[#e8f0e8] text-sm">{formatType(tool.type)}</h2>
            <button type="button" onClick={onClose} className="text-[#6e8c6e] hover:text-[#e8f0e8] transition-colors text-lg leading-none">✕</button>
          </div>

          {queuedId ? (
            <div className="px-5 py-8 flex flex-col items-center gap-4 text-center">
              <CheckCircle className="text-[#00C853]" size={32} strokeWidth={1.5} />
              <p className="font-heading font-semibold text-[#e8f0e8] text-sm">Queued successfully</p>
              <div className="w-full space-y-1">
                <p className={labelClass}>Execution ID</p>
                <p className="text-xs font-mono text-[#a0b8a0] select-all break-all">{queuedId}</p>
              </div>
              <Link href="/executions" className="text-xs font-mono text-[#00C853] underline underline-offset-2 hover:text-[#00a844] transition-colors">
                View in Executions
              </Link>
              <button type="button" onClick={onClose} className="border border-[#1a2a1a] text-[#e8f0e8] rounded-sm px-3 py-2 text-xs font-mono hover:bg-[#1a1a1a] transition-colors w-full">
                Close
              </button>
            </div>
          ) : (
            <>
              <div className="px-5 py-5 space-y-4">
                <p className={labelClass}>Payload</p>

                <div className="space-y-1.5">
                  <label className="text-xs font-mono text-[#a0b8a0]">JSON Payload</label>
                  <textarea
                    value={payloadText}
                    onChange={(e) => { setPayloadText(e.target.value); setPayloadError(null) }}
                    rows={6}
                    spellCheck={false}
                    className={inputClass}
                  />
                  {payloadError ? (
                    <p className="text-[10px] font-mono text-[#ff4d6d]">{payloadError}</p>
                  ) : (
                    <p className="text-[10px] font-mono text-[#6e8c6e]">Payload is passed directly to the tool. Must be valid JSON.</p>
                  )}
                </div>

                {error && <p className="text-xs font-mono text-[#ff4d6d]">{error}</p>}
              </div>

              <div className="flex items-center gap-2 px-5 py-4 border-t border-[#1a2a1a]">
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-2 text-xs font-mono transition-all disabled:opacity-50"
                >
                  {submitting ? 'Queuing…' : 'Run Tool'}
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="border border-[#1a2a1a] text-[#e8f0e8] rounded-sm px-3 py-2 text-xs font-mono hover:bg-[#1a1a1a] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
