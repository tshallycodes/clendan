'use client'

import { useState, useEffect, useRef } from 'react'
import { Eye, EyeSlash, ArrowCounterClockwise, Play } from '@phosphor-icons/react'
import { motion } from 'framer-motion'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const TOOLS = [
  'invoice_processing',
  'receipt_processing',
  'expense_control',
  'collections',
  'fraud_detection',
  'treasury',
  'compliance',
  'reconciliation',
  'revenue_recognition',
  'ai_accountant',
  'credit_underwriting',
  'document_intelligence',
  'spend_control',
] as const

type ToolName = typeof TOOLS[number]

type ResponseState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'result'; data: unknown }

const MAX_POLL_ATTEMPTS = 5
const POLL_INTERVAL_MS = 3000

export function ApiPlayground() {
  const [selectedTool, setSelectedTool] = useState<ToolName>('invoice_processing')
  const [payloadText, setPayloadText] = useState('{}')
  const [idempotencyKey, setIdempotencyKey] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [response, setResponse] = useState<ResponseState>({ kind: 'idle' })
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setIdempotencyKey(crypto.randomUUID())
    return () => { if (pollRef.current) clearTimeout(pollRef.current) }
  }, [])

  function regenerateKey() {
    setIdempotencyKey(crypto.randomUUID())
  }

  async function pollExecution(executionId: string, attempt: number) {
    if (attempt >= MAX_POLL_ATTEMPTS) {
      setResponse({ kind: 'result', data: { error: 'Polling timed out after max attempts', execution_id: executionId } })
      return
    }
    pollRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/v1/execute/${executionId}`, {
          headers: { Authorization: `Bearer ${apiKey}` },
        })
        const json: unknown = await res.json()
        const inner = ((json as Record<string, unknown>)?.['data']) as Record<string, unknown> | undefined
        const status = inner?.['status'] as string | undefined
        if (status === 'queued' || status === 'running') {
          await pollExecution(executionId, attempt + 1)
        } else {
          setResponse({ kind: 'result', data: json })
        }
      } catch {
        setResponse({ kind: 'result', data: { error: 'Polling request failed' } })
      }
    }, POLL_INTERVAL_MS)
  }

  async function handleRun() {
    if (pollRef.current) clearTimeout(pollRef.current)

    let parsedPayload: unknown
    try {
      parsedPayload = JSON.parse(payloadText)
    } catch {
      setResponse({ kind: 'result', data: { error: 'Invalid JSON in payload' } })
      return
    }

    setResponse({ kind: 'loading' })

    try {
      const res = await fetch(`${API}/v1/execute`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Idempotency-Key': idempotencyKey,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tool: selectedTool, payload: parsedPayload }),
      })
      const json: unknown = await res.json()
      const inner = ((json as Record<string, unknown>)?.['data']) as Record<string, unknown> | undefined
      const status = inner?.['status'] as string | undefined
      const executionId = inner?.['execution_id'] as string | undefined

      if (status === 'queued' && executionId) {
        await pollExecution(executionId, 0)
      } else {
        setResponse({ kind: 'result', data: json })
      }
    } catch {
      setResponse({ kind: 'result', data: { error: 'Request failed — check API URL and key' } })
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-4"
    >
      <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">API Playground</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Left — inputs */}
        <div className="space-y-4">

          {/* Tool selector */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Tool</label>
            <select
              value={selectedTool}
              onChange={(e) => setSelectedTool(e.target.value as ToolName)}
              className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text rounded-sm px-3 py-2 text-xs font-mono outline-none appearance-none cursor-pointer"
            >
              {TOOLS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {/* Payload editor */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Payload (JSON)</label>
            <textarea
              value={payloadText}
              onChange={(e) => setPayloadText(e.target.value)}
              rows={6}
              spellCheck={false}
              className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none resize-none"
            />
          </div>

          {/* Idempotency Key */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Idempotency Key</label>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={idempotencyKey}
                className="flex-1 min-w-0 bg-brand-bg border border-brand-border text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none cursor-default"
              />
              <button
                type="button"
                onClick={regenerateKey}
                className="shrink-0 flex items-center gap-1 border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-2.5 py-2 text-xs font-mono transition-colors"
              >
                <ArrowCounterClockwise className="w-3.5 h-3.5" /> Regenerate
              </button>
            </div>
          </div>

          {/* API Key */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">API Key</label>
            <div className="flex items-center gap-2">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="ck_live_..."
                className="flex-1 min-w-0 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none"
              />
              <button
                type="button"
                onClick={() => setShowApiKey((v) => !v)}
                className="shrink-0 border border-brand-border text-brand-muted hover:text-brand-text hover:bg-brand-elevated rounded-sm p-2 transition-colors"
                aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
              >
                {showApiKey ? <EyeSlash className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Run button */}
          <button
            type="button"
            onClick={handleRun}
            disabled={response.kind === 'loading'}
            className="flex items-center gap-2 bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-mono font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="w-3.5 h-3.5" weight="fill" />
            {response.kind === 'loading' ? 'Executing…' : 'Run'}
          </button>
        </div>

        {/* Right — response panel */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Response</label>
          <div className="bg-brand-bg border border-brand-border rounded-sm p-4 min-h-[280px] overflow-auto">
            {response.kind === 'idle' && (
              <p className="text-xs font-mono text-brand-muted">Response will appear here</p>
            )}
            {response.kind === 'loading' && (
              <p className="text-xs font-mono text-brand-muted animate-pulse">Executing...</p>
            )}
            {response.kind === 'result' && (
              <pre className="text-xs font-mono text-brand-text whitespace-pre-wrap break-all">
                {JSON.stringify(response.data, null, 2)}
              </pre>
            )}
          </div>
        </div>

      </div>
    </motion.div>
  )
}
