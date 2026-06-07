'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { Copy, Check, Plus, X } from 'lucide-react'
import { useCanConfigure } from '@/lib/auth-client'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface ApiKey {
  id: string; name: string; key_prefix: string
  status: string; created_at: string; expires_at: string | null
}

export function ApiKeysSection() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [revealedKey, setRevealedKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  async function fetchKeys() {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/api-keys`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) {
        const json = await res.json()
        setKeys(json.data.api_keys)
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

  async function copyKey() {
    if (!revealedKey) return
    await navigator.clipboard.writeText(revealedKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-4">
      {revealedKey && (
        <div className="border border-brand-green/40 bg-brand-green/05 rounded-sm p-4 space-y-3">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-green">New API key — copy it now. It will not be shown again.</p>
          <div className="flex items-center gap-3 bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
            <code className="flex-1 text-xs font-mono text-brand-text break-all">{revealedKey}</code>
            <button type="button" onClick={copyKey} aria-label="Copy API key" className="shrink-0 text-brand-muted hover:text-brand-text transition-colors">
              {copied ? <Check className="w-4 h-4 text-brand-green" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <button type="button" onClick={() => setRevealedKey(null)} className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors">
            I've copied it — dismiss
          </button>
        </div>
      )}

      {showForm && canConfigure && (
        <div className="flex items-center gap-3 bg-brand-surface border border-brand-border rounded-sm p-3">
          <input
            autoFocus value={newName} onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Key name (e.g. Production, CI/CD)"
            className="flex-1 bg-brand-bg border border-brand-border focus:border-brand-green text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none"
          />
          <button type="button" onClick={handleCreate} disabled={creating || !newName.trim()}
            className="bg-brand-green text-black hover:bg-[#00a844] rounded-sm px-4 py-2 text-xs font-mono disabled:opacity-40 transition-colors">
            {creating ? 'Generating...' : 'Generate'}
          </button>
          <button type="button" aria-label="Cancel" onClick={() => { setShowForm(false); setNewName('') }} className="text-brand-muted hover:text-brand-text transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {loading ? (
        <p className="text-xs font-mono text-brand-muted py-4">Loading...</p>
      ) : keys.length === 0 && !showForm ? (
        <p className="text-xs font-mono text-brand-muted py-4">No API keys — generate your first key to connect external systems.</p>
      ) : (
        <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
          {keys.map((k) => (
            <div key={k.id} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <span className="text-xs font-mono text-brand-text">{k.name}</span>
                <code className="ml-3 text-[10px] font-mono text-brand-muted">{k.key_prefix}••••••••</code>
              </div>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${k.status === 'active' ? 'text-brand-green border-brand-green/30 bg-brand-green/08' : 'text-brand-muted border-brand-border'}`}>
                {k.status}
              </span>
              <span className="text-[10px] font-mono text-brand-muted hidden sm:block">
                {new Date(k.created_at).toLocaleDateString()}
              </span>
              {k.status === 'active' && canConfigure && (
                <button type="button" onClick={() => handleRevoke(k.id)}
                  className="text-[10px] font-mono text-brand-danger border border-brand-danger/30 bg-brand-danger/08 hover:bg-brand-danger/15 rounded-sm px-2 py-0.5 transition-colors">
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!showForm && canConfigure && (
        <button type="button" onClick={() => setShowForm(true)}
          className="flex items-center gap-2 text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-3 py-2 transition-colors">
          <Plus className="w-3.5 h-3.5" />
          Generate API Key
        </button>
      )}
    </div>
  )
}
