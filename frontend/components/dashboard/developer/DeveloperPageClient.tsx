'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { Copy, Check, ArrowSquareOut, Plus, X, Lightning, GitBranch, ShieldCheck, Trash } from '@phosphor-icons/react'
import { useToast } from '@/components/Providers'
import { motion } from 'framer-motion'
import { CodeBlock } from '@/components/dashboard/api/CodeBlock'
import { ApiPlayground } from './ApiPlayground'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BASE_URL = 'https://api.clendan.com'
const DOCS_URL = 'https://clendan.mintlify.app'

const RESPONSE_SHAPE = `{
  "data": { ... },
  "error": null,
  "trace_id": "trc_01j...",
  "timestamp": "2026-01-15T10:30:00Z"
}`

type Lang = 'python' | 'javascript' | 'curl'

const SNIPPETS: Record<Lang, string> = {
  python: `import requests

response = requests.post(
    "https://api.clendan.com/execute",
    headers={
        "Authorization": "ck_live_...",
        "Idempotency-Key": "unique-key-here",
    },
    json={
        "tool": "invoice_processing",
        "payload": {}
    }
)
print(response.json())`,

  javascript: `const response = await fetch(
  "https://api.clendan.com/execute",
  {
    method: "POST",
    headers: {
      "Authorization": "ck_live_...",
      "Idempotency-Key": crypto.randomUUID(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      tool: "invoice_processing",
      payload: {},
    }),
  }
);

const data = await response.json();`,

  curl: `curl -X POST https://api.clendan.com/execute \\
  -H "Authorization: ck_live_..." \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -H "Content-Type: application/json" \\
  -d '{"tool": "invoice_processing", "payload": {}}'`,
}

interface ApiKey {
  id: string; name: string; key_prefix: string; status: string
  created_at: string; expires_at: string | null
}

const EASE = [0.25, 0.46, 0.45, 0.94] as const
const pageVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const fadeUp = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: EASE } } }

const CAPABILITIES = [
  { icon: Lightning, title: 'Execute Tools', desc: 'Trigger any deployed AI tool via a single POST endpoint.' },
  { icon: GitBranch, title: 'Webhooks', desc: 'Real-time events when agents complete tasks or require approval.' },
  { icon: ShieldCheck, title: 'Audit Trail', desc: 'Query the full immutable log of every agent action.' },
]

const ENDPOINTS = [
  { method: 'POST', path: '/execute',                        desc: 'Trigger any deployed tool' },
  { method: 'POST', path: '/execute/document-intelligence',  desc: 'Upload file for analysis' },
  { method: 'GET',  path: '/execute/{execution_id}',         desc: 'Poll execution result' },
  { method: 'GET',  path: '/execute/tools',                  desc: 'List deployed tools' },
  { method: 'GET',  path: '/execute/stats',                  desc: 'Aggregate execution counts' },
  { method: 'GET',  path: '/execute/approvals',              desc: 'List pending approvals' },
  { method: 'POST', path: '/execute/approvals/{id}/approve', desc: 'Approve an agent action' },
  { method: 'POST', path: '/execute/approvals/{id}/reject',  desc: 'Reject an agent action' },
  { method: 'GET',  path: '/execute/audit',                  desc: 'Query immutable audit log' },
  { method: 'GET',  path: '/execute/transactions',           desc: 'List synced transactions' },
]

const WEBHOOK_EVENTS = [
  { event: 'tool.executed',          desc: 'Tool completed execution' },
  { event: 'tool.approval_required', desc: 'Human approval needed' },
  { event: 'tool.policy_blocked',    desc: 'Policy engine blocked action' },
  { event: 'reconciliation.complete', desc: 'Reconciliation run finished' },
  { event: 'invoice.processed',      desc: 'Invoice classified and routed' },
  { event: 'transaction.synced',     desc: 'New transactions ingested' },
  { event: 'audit.written',          desc: 'Audit log entry created' },
]

const METHOD_COLORS: Record<string, string> = {
  GET:  'text-[#00a8cc] border-[rgba(0,168,204,0.3)] bg-[rgba(0,168,204,0.08)]',
  POST: 'text-[#00C853] border-[rgba(0,200,83,0.3)] bg-[rgba(0,200,83,0.08)]',
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  async function copy() { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  return (
    <button type="button" onClick={copy} aria-label="Copy" className="shrink-0 text-brand-muted hover:text-brand-text transition-colors">
      {copied ? <Check className="w-4 h-4 text-[#00C853]" /> : <Copy className="w-4 h-4" />}
    </button>
  )
}

function ApiKeysSection({ keys, loading, showForm, setShowForm, newName, setNewName, creating, handleCreate, handleRevoke, handleDelete, revealedKey, setRevealedKey }: {
  keys: ApiKey[]; loading: boolean; showForm: boolean; setShowForm: (v: boolean) => void
  newName: string; setNewName: (v: string) => void; creating: boolean
  handleCreate: () => void; handleRevoke: (id: string) => void; handleDelete: (id: string) => void
  revealedKey: string | null; setRevealedKey: (v: string | null) => void
}) {
  const [copiedKey, setCopiedKey] = useState(false)
  async function copyKey() { if (!revealedKey) return; await navigator.clipboard.writeText(revealedKey); setCopiedKey(true); setTimeout(() => setCopiedKey(false), 2000) }
  return (
    <div className="space-y-3">
      {revealedKey && (
        <div className="border border-[rgba(0,200,83,0.4)] bg-[rgba(0,200,83,0.05)] rounded-sm p-4 space-y-3">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#00C853]">New key — copy it now. It will not be shown again.</p>
          <div className="flex items-center gap-3 bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
            <code className="flex-1 text-xs font-mono text-brand-text break-all">{revealedKey}</code>
            <button type="button" onClick={copyKey} className="shrink-0 text-brand-muted hover:text-brand-text transition-colors">
              {copiedKey ? <Check className="w-4 h-4 text-[#00C853]" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <button type="button" onClick={() => setRevealedKey(null)} className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors">I&apos;ve copied it — dismiss</button>
        </div>
      )}
      {showForm && (
        <div className="flex items-center gap-3 bg-brand-surface border border-brand-border rounded-sm p-3">
          <input autoFocus value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Key name (e.g. Production, CI/CD)"
            className="flex-1 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none" />
          <button type="button" onClick={handleCreate} disabled={creating || !newName.trim()}
            className="bg-[#00C853] text-black hover:bg-[#00a844] rounded-sm px-4 py-2 text-xs font-mono disabled:opacity-40 transition-colors active:scale-[0.97]">
            {creating ? 'Generating…' : 'Generate'}
          </button>
          <button type="button" onClick={() => { setShowForm(false); setNewName('') }} className="text-brand-muted hover:text-brand-text transition-colors"><X className="w-4 h-4" /></button>
        </div>
      )}
      {loading ? (
        <p className="text-xs font-mono text-brand-muted py-4">Loading…</p>
      ) : keys.length === 0 && !showForm ? (
        <p className="text-xs font-mono text-brand-muted py-2">No API keys yet — generate one to start.</p>
      ) : (
        <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
          {keys.map((k) => (
            <div key={k.id} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <span className="text-xs font-mono text-brand-text">{k.name}</span>
                <code className="ml-3 text-[10px] font-mono text-brand-muted">{k.key_prefix}••••••••</code>
              </div>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${k.status === 'active' ? 'text-[#00C853] border-[rgba(0,200,83,0.3)] bg-[rgba(0,200,83,0.08)]' : 'text-brand-muted border-brand-border'}`}>{k.status}</span>
              <span className="text-[10px] font-mono text-brand-muted hidden sm:block">{new Date(k.created_at).toLocaleDateString()}</span>
              {k.status === 'active' && (
                <button type="button" onClick={() => handleRevoke(k.id)}
                  className="text-[10px] font-mono text-[#ff4d6d] border border-[rgba(255,77,109,0.3)] bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.15)] rounded-sm px-2 py-0.5 transition-colors">
                  Revoke
                </button>
              )}
              <button type="button" onClick={() => handleDelete(k.id)}
                className="shrink-0 text-brand-muted hover:text-[#ff4d6d] transition-colors p-0.5">
                <Trash className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
      {!showForm && (
        <button type="button" onClick={() => setShowForm(true)}
          className="flex items-center gap-2 text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-3 py-2 transition-colors">
          <Plus className="w-3.5 h-3.5" /> Generate API Key
        </button>
      )}
    </div>
  )
}

export function DeveloperPageClient() {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [revealedKey, setRevealedKey] = useState<string | null>(null)
  const [lang, setLang] = useState<Lang>('python')

  async function fetchKeys() {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/api-keys`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) { const json = await res.json(); setKeys(json.data.api_keys ?? []) }
      else toast('Failed to load API keys', 'error')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchKeys() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate() {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/api-keys`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim() }),
      })
      if (res.ok) { const json = await res.json(); setRevealedKey(json.data.key); toast('API key generated — copy it now', 'success'); setNewName(''); setShowForm(false); await fetchKeys() }
      else toast('Failed to generate API key', 'error')
    } finally { setCreating(false) }
  }

  async function handleRevoke(id: string) {
    try {
      const token = await getToken()
      await fetch(`${API}/api-keys/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
      await fetchKeys(); toast('API key revoked', 'success')
    } catch { toast('Failed to revoke key', 'error') }
  }

  async function handleDelete(id: string) {
    try {
      const token = await getToken()
      await fetch(`${API}/api-keys/${id}/permanent`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
      await fetchKeys(); toast('API key deleted', 'success')
    } catch { toast('Failed to delete key', 'error') }
  }

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-8">

      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Developer</h1>
          <p className="text-xs font-mono text-brand-muted mt-1">
            Connect external systems to Clendan — execute tools, receive webhooks, query audit logs.
          </p>
        </div>
        <a href={DOCS_URL} target="_blank" rel="noopener noreferrer"
          className="shrink-0 flex items-center gap-1.5 text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-bg rounded-sm px-3 py-1.5 transition-colors">
          API Reference <ArrowSquareOut className="w-3 h-3" />
        </a>
      </motion.div>

      {/* Info strip */}
      <motion.div variants={fadeUp} className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-1">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Base URL</p>
          <div className="flex items-center gap-2">
            <code className="text-xs font-mono text-brand-text flex-1 truncate">{BASE_URL}</code>
            <CopyButton text={BASE_URL} />
          </div>
        </div>
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-1">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Authentication</p>
          <div className="flex items-center gap-1.5">
            <code className="text-[10px] font-mono text-brand-muted">Authorization:</code>
            <code className="text-xs font-mono text-brand-text">ck_live_...</code>
          </div>
        </div>
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-1">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Rate Limit</p>
          <code className="text-xs font-mono text-brand-text">60–200 req / min</code>
        </div>
        <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-1">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Idempotency</p>
          <code className="text-xs font-mono text-brand-text">Required on writes</code>
        </div>
      </motion.div>

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_1fr] gap-6">

        {/* Left column */}
        <div className="space-y-8">

          {/* Capabilities */}
          <motion.div variants={fadeUp} className="space-y-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">What you can build</p>
            <div className="space-y-2">
              {CAPABILITIES.map(({ icon: Icon, title, desc }) => (
                <div key={title} className="bg-brand-surface border border-brand-border rounded-sm p-4 flex items-start gap-3">
                  <Icon className="w-4 h-4 text-[#00C853] shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-mono font-medium text-brand-text">{title}</p>
                    <p className="text-[11px] font-mono text-brand-muted mt-0.5 leading-relaxed">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* API Keys */}
          <motion.div variants={fadeUp} className="space-y-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">API Keys</p>
            <ApiKeysSection keys={keys} loading={loading} showForm={showForm} setShowForm={setShowForm}
              newName={newName} setNewName={setNewName} creating={creating}
              handleCreate={handleCreate} handleRevoke={handleRevoke} handleDelete={handleDelete}
              revealedKey={revealedKey} setRevealedKey={setRevealedKey} />
          </motion.div>

          {/* Quick Start */}
          <motion.div variants={fadeUp} className="space-y-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Quick Start</p>
            <div className="flex gap-1">
              {(['python', 'javascript', 'curl'] as Lang[]).map((l) => (
                <button key={l} type="button" onClick={() => setLang(l)}
                  className={`px-2.5 py-1 text-[10px] font-mono rounded-sm transition-colors ${lang === l ? 'bg-brand-elevated border border-brand-border text-brand-text' : 'text-brand-muted hover:text-brand-secondary'}`}>
                  {l}
                </button>
              ))}
            </div>
            <CodeBlock code={SNIPPETS[lang]} lang={lang} />
          </motion.div>

          {/* Playground */}
          <motion.div variants={fadeUp}>
            <ApiPlayground />
          </motion.div>

        </div>

        {/* Right column */}
        <div className="space-y-8">

          {/* Endpoints */}
          <motion.div variants={fadeUp} className="space-y-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">REST Endpoints</p>
            <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
              {ENDPOINTS.map(({ method, path, desc }) => (
                <div key={path} className="bg-brand-surface px-4 py-2.5 flex items-center gap-3">
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-sm border shrink-0 ${METHOD_COLORS[method] ?? 'text-brand-muted border-brand-border'}`}>{method}</span>
                  <code className="text-xs font-mono text-brand-text flex-1 truncate">{path}</code>
                  <span className="text-[11px] font-mono text-brand-muted hidden sm:block shrink-0">{desc}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Webhook events */}
          <motion.div variants={fadeUp} className="space-y-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Webhook Events</p>
            <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
              {WEBHOOK_EVENTS.map(({ event, desc }) => (
                <div key={event} className="bg-brand-surface px-4 py-2.5 flex items-center gap-4">
                  <code className="text-xs font-mono text-[#00a8cc] flex-1">{event}</code>
                  <span className="text-[11px] font-mono text-brand-muted shrink-0 hidden sm:block">{desc}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Response shape */}
          <motion.div variants={fadeUp} className="space-y-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Standard Response Shape</p>
            <CodeBlock code={RESPONSE_SHAPE} lang="json" />
          </motion.div>

        </div>
      </div>

    </motion.div>
  )
}
