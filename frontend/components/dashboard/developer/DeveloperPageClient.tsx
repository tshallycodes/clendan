'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { Copy, Check, ExternalLink, Plus, X } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BASE_URL = 'https://api.clendan.com/v1'
const QUICK_START = `curl -X POST https://api.clendan.com/v1/execute \\
  -H "Authorization: Bearer ck_live_..." \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -H "Content-Type: application/json" \\
  -d '{"tool": "document_intelligence", "payload": {}}'`

interface ApiKey {
  id: string
  name: string
  key_prefix: string
  status: string
  created_at: string
  expires_at: string | null
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  async function handleCopy() {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button type="button" onClick={handleCopy} aria-label="Copy to clipboard"
      className="shrink-0 text-brand-muted hover:text-brand-text transition-colors">
      {copied ? <Check className="w-4 h-4 text-[#00C853]" /> : <Copy className="w-4 h-4" />}
    </button>
  )
}

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted mb-3">
      {children}
    </p>
  )
}

export function DeveloperPageClient() {
  const { getToken } = useAuth()
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [revealedKey, setRevealedKey] = useState<string | null>(null)
  const [copiedKey, setCopiedKey] = useState(false)

  async function fetchKeys() {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/api-keys`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) {
        const json = await res.json()
        setKeys(json.data.api_keys ?? [])
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchKeys() }, [])

  async function handleCreate() {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/api-keys`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim() }),
      })
      if (res.ok) {
        const json = await res.json()
        setRevealedKey(json.data.key)
        setNewName('')
        setShowForm(false)
        await fetchKeys()
      }
    } finally {
      setCreating(false)
    }
  }

  async function handleRevoke(id: string) {
    const token = await getToken()
    await fetch(`${API}/v1/api-keys/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
    await fetchKeys()
  }

  async function copyRevealedKey() {
    if (!revealedKey) return
    await navigator.clipboard.writeText(revealedKey)
    setCopiedKey(true)
    setTimeout(() => setCopiedKey(false), 2000)
  }

  return (
    <div className="p-6 max-w-2xl space-y-10">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Developer</h1>
        <p className="text-brand-secondary text-xs font-mono mt-1">
          Connect external systems to Clendan via API key.
        </p>
      </div>

      <section className="space-y-3">
        <SectionLabel>API Keys</SectionLabel>

        {revealedKey && (
          <div className="border border-[#00C853]/40 bg-[rgba(0,200,83,0.05)] rounded-sm p-4 space-y-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#00C853]">
              New API key — copy it now. It will not be shown again.
            </p>
            <div className="flex items-center gap-3 bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
              <code className="flex-1 text-xs font-mono text-brand-text break-all">{revealedKey}</code>
              <button type="button" onClick={copyRevealedKey} aria-label="Copy API key"
                className="shrink-0 text-brand-muted hover:text-brand-text transition-colors">
                {copiedKey ? <Check className="w-4 h-4 text-[#00C853]" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <button type="button" onClick={() => setRevealedKey(null)}
              className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors">
              I&apos;ve copied it — dismiss
            </button>
          </div>
        )}

        {showForm && (
          <div className="flex items-center gap-3 bg-brand-surface border border-brand-border rounded-sm p-3">
            <input
              autoFocus value={newName} onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              placeholder="Key name (e.g. Production, CI/CD)"
              className="flex-1 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none"
            />
            <button type="button" onClick={handleCreate} disabled={creating || !newName.trim()}
              className="bg-[#00C853] text-black hover:bg-[#00a844] rounded-sm px-4 py-2 text-xs font-mono disabled:opacity-40 transition-colors active:scale-[0.97]">
              {creating ? 'Generating...' : 'Generate'}
            </button>
            <button type="button" aria-label="Cancel" onClick={() => { setShowForm(false); setNewName('') }}
              className="text-brand-muted hover:text-brand-text transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {loading ? (
          <p className="text-xs font-mono text-brand-muted py-4">Loading...</p>
        ) : keys.length === 0 && !showForm ? (
          <p className="text-xs font-mono text-brand-muted py-4">
            No API keys — generate your first key to connect external systems.
          </p>
        ) : (
          <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
            {keys.map((k) => (
              <div key={k.id} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-mono text-brand-text">{k.name}</span>
                  <code className="ml-3 text-[10px] font-mono text-brand-muted">{k.key_prefix}••••••••</code>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${
                  k.status === 'active'
                    ? 'text-[#00C853] border-[rgba(0,200,83,0.3)] bg-[rgba(0,200,83,0.08)]'
                    : 'text-brand-muted border-brand-border'
                }`}>
                  {k.status}
                </span>
                <span className="text-[10px] font-mono text-brand-muted hidden sm:block">
                  {new Date(k.created_at).toLocaleDateString()}
                </span>
                {k.status === 'active' && (
                  <button type="button" onClick={() => handleRevoke(k.id)}
                    className="text-[10px] font-mono text-[#ff4d6d] border border-[rgba(255,77,109,0.3)] bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.15)] rounded-sm px-2 py-0.5 transition-colors">
                    Revoke
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {!showForm && (
          <button type="button" onClick={() => setShowForm(true)}
            className="flex items-center gap-2 text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-3 py-2 transition-colors">
            <Plus className="w-3.5 h-3.5" />
            Generate API Key
          </button>
        )}
      </section>

      <section className="space-y-3">
        <SectionLabel>Base URL</SectionLabel>
        <div className="flex items-center gap-3 bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
          <code className="flex-1 font-mono text-xs text-brand-text">{BASE_URL}</code>
          <CopyButton text={BASE_URL} />
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Quick Start</SectionLabel>
        <div className="flex items-start gap-3 bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
          <pre className="flex-1 font-mono text-xs text-brand-text whitespace-pre-wrap break-all">{QUICK_START}</pre>
          <CopyButton text={QUICK_START} />
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Documentation</SectionLabel>
        <a href="https://clendan.mintlify.app" target="_blank" rel="noopener noreferrer"
          className="bg-brand-surface border border-brand-border rounded-sm p-4 flex items-center justify-between hover:bg-brand-elevated transition-colors">
          <div className="space-y-0.5">
            <p className="text-sm font-mono text-brand-text">API Reference</p>
            <p className="text-xs font-mono text-brand-muted">Full endpoint reference with examples</p>
          </div>
          <ExternalLink className="w-4 h-4 text-brand-muted shrink-0" />
        </a>
      </section>
    </div>
  )
}
