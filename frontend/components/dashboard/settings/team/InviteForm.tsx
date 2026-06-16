'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { Check } from 'lucide-react'
import { ROLE_LABEL } from './types'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const INVITE_ROLES = ['org:admin', 'org:approver', 'org:viewer'] as const
type InviteRole = (typeof INVITE_ROLES)[number]

interface Props {
  onInvited: () => void
}

export function InviteForm({ onInvited }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<InviteRole>('org:viewer')
  const [sending, setSending] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setSending(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/organisations/me/invitations`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), role }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Failed to send invitation')
        toast((json as { error?: string }).error ?? 'Failed to send invitation', 'error')
        return
      }
      setSuccess(true)
      toast('Invitation sent', 'success')
      setEmail('')
      setRole('org:viewer')
      onInvited()
      setTimeout(() => setSuccess(false), 3000)
    } finally {
      setSending(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-3 flex-wrap">
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="colleague@company.com"
        className="flex-1 min-w-[200px] bg-brand-bg border border-brand-border focus:border-brand-green text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-2 text-xs font-mono outline-none transition-colors"
      />
      <select
        value={role}
        onChange={(e) => setRole(e.target.value as InviteRole)}
        className="bg-brand-bg border border-brand-border focus:border-brand-green text-brand-text rounded-sm px-3 py-2 text-xs font-mono outline-none transition-colors"
      >
        {INVITE_ROLES.map((r) => (
          <option key={r} value={r}>{ROLE_LABEL[r]}</option>
        ))}
      </select>
      <button
        type="submit"
        disabled={sending || !email.trim()}
        className="bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-mono font-medium transition-all disabled:opacity-40 flex items-center gap-2"
      >
        {success ? (
          <><Check className="w-3.5 h-3.5" /> Sent</>
        ) : sending ? 'Sending…' : 'Send invite'}
      </button>
      {error && <p className="w-full text-[10px] font-mono text-brand-danger">{error}</p>}
    </form>
  )
}
