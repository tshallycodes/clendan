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
  | { kind: 'loading'; attempt?: number }
  | { kind: 'result'; data: unknown }

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE'

interface AiAccountantEndpoint {
  id: string
  method: HttpMethod
  path: string
  description: string
  defaultBody: string | null
  defaultPathParam: string | null
}

const MAX_POLL_ATTEMPTS = 20
const POLL_INTERVAL_MS = 4000

const DEFAULT_PAYLOADS: Record<ToolName, object> = {
  invoice_processing:    { invoice_id: 'inv_001', amount_minor: 125000, currency: 'GBP', vendor: 'Acme Ltd' },
  receipt_processing:    { receipt_id: 'rec_001', amount_minor: 4250, currency: 'GBP', merchant: 'Pret A Manger' },
  expense_control:       { employee_id: 'emp_001', amount_minor: 8500, currency: 'GBP', category: 'travel', description: 'Train to London' },
  collections:           { invoice_id: 'inv_001', outstanding_cents: 250000, due_date: '2026-05-01', contact_email: 'finance@client.com' },
  fraud_detection:       { transaction_id: 'txn_001', amount_minor: 99900, currency: 'GBP', merchant: 'Unknown Vendor', country: 'NG' },
  treasury:              { account_id: 'acc_001', balance_minor: 5000000, currency: 'GBP', forecast_days: 30 },
  compliance:            { entity_id: 'ent_001', entity_type: 'vendor', jurisdiction: 'GB' },
  reconciliation:        { period_start: '2026-05-01', period_end: '2026-05-31', policy: { unmatched_pct_threshold: 0.2, match_date_window_days: 30, match_amount_tolerance_pct: 0.01, include_reconciled: false } },
  revenue_recognition:   { contract_id: 'con_001', amount_minor: 1200000, currency: 'GBP', start_date: '2026-01-01', end_date: '2026-12-31' },
  ai_accountant:         { query: 'Summarise outstanding liabilities for May 2026', context: 'month-end review' },
  credit_underwriting:   { applicant_id: 'app_001', requested_amount_minor: 5000000, currency: 'GBP', term_months: 12 },
  document_intelligence: { document_id: 'doc_001', document_type: 'invoice', source: 'email_attachment' },
  spend_control:         { employee_id: 'emp_001', amount_minor: 35000, currency: 'GBP', category: 'software', vendor: 'Figma' },
}

const AI_ACCOUNTANT_ENDPOINTS: AiAccountantEndpoint[] = [
  {
    id: 'categorise',
    method: 'POST',
    path: '/v1/execute',
    description: 'Categorise transactions — enqueue the AI Accountant tool to auto-categorise the given transaction IDs.',
    defaultBody: JSON.stringify(
      {
        tool: 'ai_accountant',
        payload: { transaction_ids: ['txn_abc123', 'txn_def456'] },
      },
      null,
      2,
    ),
    defaultPathParam: null,
  },
  {
    id: 'get-transactions',
    method: 'GET',
    path: '/v1/transactions?status=pending&limit=50',
    description: 'Get transactions — list transactions processed by the AI Accountant, filtered by status.',
    defaultBody: null,
    defaultPathParam: null,
  },
  {
    id: 'correct-category',
    method: 'PATCH',
    path: '/v1/transactions/{transaction_id}/category',
    description: 'Correct transaction category — override the AI-assigned category for a specific transaction.',
    defaultBody: JSON.stringify({ category: 'software' }, null, 2),
    defaultPathParam: 'txn_abc123',
  },
  {
    id: 'month-end-close',
    method: 'POST',
    path: '/v1/close-runs',
    description: 'Trigger month-end close — orchestrate the close process for the given accounting period.',
    defaultBody: JSON.stringify({ period: '2025-01' }, null, 2),
    defaultPathParam: null,
  },
  {
    id: 'payroll-reconciliation',
    method: 'POST',
    path: '/v1/payroll-runs',
    description: 'Run payroll reconciliation — match payroll payments against the provided roster and flag discrepancies.',
    defaultBody: JSON.stringify(
      {
        period: '2025-01',
        roster: [
          { name: 'Jane Smith', expected_minor: 450000 },
          { name: 'John Doe', expected_minor: 380000 },
        ],
      },
      null,
      2,
    ),
    defaultPathParam: null,
  },
  {
    id: 'journal-entry',
    method: 'POST',
    path: '/v1/journal-entries',
    description: 'Create journal entry — post a double-entry journal to the connected accounting system.',
    defaultBody: JSON.stringify(
      {
        period: '2025-01',
        description: 'January 2025 Payroll',
        lines: [
          { account_code: '5000', account_name: 'Payroll Expense - Engineering', debit_minor: 4500000, credit_minor: 0 },
          { account_code: '1010', account_name: 'Business Current Account', debit_minor: 0, credit_minor: 4500000 },
        ],
      },
      null,
      2,
    ),
    defaultPathParam: null,
  },
]

const METHOD_COLORS: Record<HttpMethod, string> = {
  GET:    'text-[#00C853]',
  POST:   'text-[#00a8cc]',
  PATCH:  'text-[#f5a623]',
  DELETE: 'text-[#ff4d6d]',
}

// ---------------------------------------------------------------------------
// AiAccountantEndpointRow — one interactive row per endpoint
// ---------------------------------------------------------------------------
interface AiAccountantEndpointRowProps {
  endpoint: AiAccountantEndpoint
  apiKey: string
  idempotencyKey: string
}

function AiAccountantEndpointRow({ endpoint, apiKey, idempotencyKey }: AiAccountantEndpointRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [bodyText, setBodyText] = useState(endpoint.defaultBody ?? '')
  const [pathParam, setPathParam] = useState(endpoint.defaultPathParam ?? '')
  const [resp, setResp] = useState<ResponseState>({ kind: 'idle' })

  function resolvedPath(): string {
    if (endpoint.defaultPathParam !== null) {
      return endpoint.path.replace('{transaction_id}', pathParam || 'txn_abc123')
    }
    return endpoint.path
  }

  async function run() {
    setResp({ kind: 'loading' })

    const url = `${API}${resolvedPath()}`
    const hasBody = endpoint.defaultBody !== null

    let parsedBody: unknown
    if (hasBody) {
      try {
        parsedBody = JSON.parse(bodyText)
      } catch {
        setResp({ kind: 'result', data: { error: 'Invalid JSON in body' } })
        return
      }
    }

    const headers: Record<string, string> = { Authorization: apiKey }
    if (endpoint.method !== 'GET') {
      headers['Idempotency-Key'] = idempotencyKey
    }
    if (hasBody) {
      headers['Content-Type'] = 'application/json'
    }

    try {
      const res = await fetch(url, {
        method: endpoint.method,
        headers,
        ...(hasBody ? { body: JSON.stringify(parsedBody) } : {}),
      })
      const json: unknown = await res.json()
      setResp({ kind: 'result', data: json })
    } catch {
      setResp({ kind: 'result', data: { error: 'Request failed — check API URL and key' } })
    }
  }

  return (
    <div className="border border-brand-border rounded-sm bg-brand-surface">
      {/* Header row */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-brand-elevated transition-colors text-left"
      >
        <span className={`shrink-0 text-[10px] font-mono font-semibold uppercase tracking-wider w-10 ${METHOD_COLORS[endpoint.method]}`}>
          {endpoint.method}
        </span>
        <span className="flex-1 min-w-0 text-xs font-mono text-brand-text truncate">{endpoint.path}</span>
        <span className="shrink-0 text-[10px] font-mono text-brand-muted hidden sm:block">{endpoint.description.split('—')[0].trim()}</span>
      </button>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t border-brand-border px-3 pb-3 pt-3 space-y-3">
          <p className="text-[10px] font-mono text-brand-muted">{endpoint.description}</p>

          {/* Path param input (only for PATCH with {transaction_id}) */}
          {endpoint.defaultPathParam !== null && (
            <div className="space-y-1">
              <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">transaction_id</label>
              <input
                value={pathParam}
                onChange={(e) => setPathParam(e.target.value)}
                placeholder="txn_abc123"
                className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none"
              />
            </div>
          )}

          {/* Body editor */}
          {endpoint.defaultBody !== null && (
            <div className="space-y-1">
              <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Body (JSON)</label>
              <textarea
                value={bodyText}
                onChange={(e) => setBodyText(e.target.value)}
                rows={Math.min(bodyText.split('\n').length + 1, 12)}
                spellCheck={false}
                className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none resize-none"
              />
            </div>
          )}

          {/* Run + response */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={run}
              disabled={resp.kind === 'loading'}
              className="flex items-center gap-1.5 bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 text-xs font-mono font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-3 h-3" weight="fill" />
              {resp.kind === 'loading' ? 'Running…' : 'Run'}
            </button>
            {resp.kind === 'result' && (
              <button
                type="button"
                onClick={() => setResp({ kind: 'idle' })}
                className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {resp.kind === 'loading' && (
            <p className="text-xs font-mono text-brand-muted animate-pulse">Waiting for response…</p>
          )}
          {resp.kind === 'result' && (
            <div className="bg-brand-bg border border-brand-border rounded-sm p-3 max-h-60 overflow-y-auto">
              <pre className="text-xs font-mono text-brand-text whitespace-pre-wrap break-all">
                {JSON.stringify(resp.data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ApiPlayground — main export
// ---------------------------------------------------------------------------
export function ApiPlayground() {
  const [tab, setTab] = useState<'execute' | 'ai-accountant'>('execute')
  const [selectedTool, setSelectedTool] = useState<ToolName>('invoice_processing')
  const [payloadText, setPayloadText] = useState(() => JSON.stringify(DEFAULT_PAYLOADS['invoice_processing'], null, 2))
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
      setResponse({ kind: 'result', data: { note: 'Job is still running. Poll manually.', execution_id: executionId } })
      return
    }
    setResponse({ kind: 'loading', attempt: attempt + 1 })
    pollRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/v1/execute/${executionId}`, {
          headers: { Authorization: apiKey },
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
          Authorization: apiKey,
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

      {/* Tab switcher */}
      <div className="flex items-center gap-1 border-b border-brand-border pb-0">
        {(['execute', 'ai-accountant'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'border-[#00C853] text-brand-text'
                : 'border-transparent text-brand-muted hover:text-brand-text'
            }`}
          >
            {t === 'execute' ? 'Execute' : 'AI Accountant'}
          </button>
        ))}
      </div>

      {/* Shared API Key (always visible) */}
      <div className="space-y-1.5">
        <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">API Key</label>
        <div className="flex items-center gap-2">
          <input
            type={showApiKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="ck_live_..."
            autoComplete="new-password"
            name="playground-api-key"
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

      {/* Execute tab */}
      {tab === 'execute' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* Left — inputs */}
          <div className="space-y-4">

            {/* Tool selector */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Tool</label>
              <select
                value={selectedTool}
                onChange={(e) => {
                  const tool = e.target.value as ToolName
                  setSelectedTool(tool)
                  setPayloadText(JSON.stringify(DEFAULT_PAYLOADS[tool], null, 2))
                }}
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

            {/* Run button */}
            <button
              type="button"
              onClick={handleRun}
              disabled={response.kind === 'loading'}
              className="flex items-center gap-2 bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-mono font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-3.5 h-3.5" weight="fill" />
              {response.kind === 'loading'
                ? response.attempt ? `Polling ${response.attempt}/${MAX_POLL_ATTEMPTS}…` : 'Queuing…'
                : 'Run'}
            </button>
          </div>

          {/* Right — response panel */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Response</label>
            <div className="bg-brand-bg border border-brand-border rounded-sm p-4 min-h-[280px] max-h-[500px] overflow-y-auto">
              {response.kind === 'idle' && (
                <p className="text-xs font-mono text-brand-muted">Response will appear here</p>
              )}
              {response.kind === 'loading' && (
                <div className="space-y-2">
                  <p className="text-xs font-mono text-brand-muted animate-pulse">
                    {response.attempt
                      ? `Polling result… (${response.attempt}/${MAX_POLL_ATTEMPTS})`
                      : 'Queuing job…'}
                  </p>
                  {response.attempt && (
                    <div className="w-full bg-brand-border rounded-full h-0.5">
                      <div
                        className="bg-[#00C853] h-0.5 rounded-full transition-all duration-500"
                        style={{ width: `${(response.attempt / MAX_POLL_ATTEMPTS) * 100}%` }}
                      />
                    </div>
                  )}
                </div>
              )}
              {response.kind === 'result' && (
                <pre className="text-xs font-mono text-brand-text whitespace-pre-wrap break-all">
                  {JSON.stringify(response.data, null, 2)}
                </pre>
              )}
            </div>
          </div>

        </div>
      )}

      {/* AI Accountant tab */}
      {tab === 'ai-accountant' && (
        <div className="space-y-2">
          <p className="text-[10px] font-mono text-brand-muted">
            Click any endpoint to expand it, edit the body, and run it against your API key above.
            POST and PATCH requests use a shared idempotency key.
          </p>
          {AI_ACCOUNTANT_ENDPOINTS.map((ep) => (
            <AiAccountantEndpointRow
              key={ep.id}
              endpoint={ep}
              apiKey={apiKey}
              idempotencyKey={idempotencyKey}
            />
          ))}
        </div>
      )}
    </motion.div>
  )
}
