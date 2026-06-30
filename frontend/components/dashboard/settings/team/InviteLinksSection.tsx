'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const EXPIRY_OPTIONS = [
  { label: '1 hour', value: 1 },
  { label: '24 hours', value: 24 },
  { label: '7 days', value: 168 },
  { label: '30 days', value: 720 },
  { label: '1 year', value: 8760 },
] as const

const ROLE_OPTIONS = ['admin', 'approver', 'viewer'] as const
type InviteLinkRole = (typeof ROLE_OPTIONS)[number]

const ROLE_LABEL: Record<InviteLinkRole, string> = {
  admin: 'Admin',
  approver: 'Approver',
  viewer: 'Viewer',
}

interface InviteLink {
  id: string
  token: string
  role: string
  created_at: string
  expires_at: string
}

function formatExpiry(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return 'Expired'
  const h = Math.floor(diff / 3600000)
  if (h < 24) return `${h}h left`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}d left`
  return `${Math.floor(d / 30)}mo left`
}

export function InviteLinksSection() {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [links, setLinks] = useState<InviteLink[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [role, setRole] = useState<InviteLinkRole>('viewer')
  const [expiresIn, setExpiresIn] = useState<number>(168)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchLinks = useCallback(async () => {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/organisations/me/invite-links`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const json = await res.json()
        setLinks((json.data ?? []) as InviteLink[])
      }
    } finally {
      setLoading(false)
    }
  }, [getToken])

  useEffect(() => {
    fetchLinks()
  }, [fetchLinks])

  async function handleCreate() {
    setCreating(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/organisations/me/invite-links`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ role, expires_in_hours: expiresIn }),
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        setError(j?.detail ?? 'Failed to create invite link')
        toast(j?.detail ?? 'Failed to create invite link', 'error')
        return
      }
      await fetchLinks()
      toast('Invite link generated', 'success')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: string) {
    const token = await getToken()
    const res = await fetch(`${API}/organisations/me/invite-links/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      setLinks((prev) => prev.filter((l) => l.id !== id))
      toast('Invite link deleted', 'success')
    } else {
      toast('Failed to delete link', 'error')
    }
  }

  function handleCopy(link: InviteLink) {
    const url = `${window.location.origin}/join/${link.token}`
    navigator.clipboard.writeText(url).then(() => {
      setCopiedId(link.id)
      toast('Link copied to clipboard', 'info')
      setTimeout(() => setCopiedId(null), 2000)
    })
  }

  const SELECT = 'bg-brand-bg border border-brand-border rounded-sm px-2 py-1.5 text-xs font-mono text-brand-text focus:border-brand-green outline-none'

  return (
    <div className="space-y-4">
      {/* Create form */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as InviteLinkRole)}
          aria-label="Role for invite link"
          className={SELECT}
        >
          {ROLE_OPTIONS.map((r) => (
            <option key={r} value={r}>{ROLE_LABEL[r]}</option>
          ))}
        </select>

        <select
          value={expiresIn}
          onChange={(e) => setExpiresIn(Number(e.target.value))}
          aria-label="Expiry duration"
          className={SELECT}
        >
          {EXPIRY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <button
          type="button"
          onClick={handleCreate}
          disabled={creating}
          className="bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 text-xs font-mono font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {creating ? 'Generating…' : '+ Generate link'}
        </button>
      </div>

      {error && <p className="text-xs font-mono text-brand-danger">{error}</p>}

      {/* Link list */}
      {loading ? (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <div key={i} className="h-10 bg-brand-surface rounded-sm animate-pulse" />
          ))}
        </div>
      ) : links.length === 0 ? (
        <p className="text-xs font-mono text-brand-muted">No active invite links.</p>
      ) : (
        <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
          {links.map((link) => {
            const url = typeof window !== 'undefined'
              ? `${window.location.origin}/join/${link.token}`
              : `/join/${link.token}`
            return (
              <div key={link.id} className="bg-brand-surface px-4 py-3 flex items-center gap-3">
                <span className="flex-1 font-mono text-xs text-brand-muted truncate" title={url}>
                  {url}
                </span>
                <span className="shrink-0 text-[10px] font-mono text-brand-muted">
                  {ROLE_LABEL[link.role.toLowerCase() as InviteLinkRole] ?? link.role}
                </span>
                <span className="shrink-0 text-[10px] font-mono text-brand-muted">
                  {formatExpiry(link.expires_at)}
                </span>
                <button
                  type="button"
                  onClick={() => handleCopy(link)}
                  className="shrink-0 text-[10px] font-mono border border-brand-border rounded-sm px-2 py-1 text-brand-text hover:border-brand-green transition-colors"
                >
                  {copiedId === link.id ? 'Copied!' : 'Copy'}
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(link.id)}
                  aria-label="Delete invite link"
                  className="shrink-0 text-[10px] font-mono text-brand-danger hover:underline transition-colors"
                >
                  Delete
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
