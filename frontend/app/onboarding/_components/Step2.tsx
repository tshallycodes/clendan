'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { InviteRow } from './InviteRow'
import type { Invitation } from './InviteRow'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const MAX_INVITES = 10

interface Step2Props {
  onNext: () => void
  onSkip: () => void
}

export function Step2({ onNext, onSkip }: Step2Props) {
  const { getToken } = useAuth()
  const [invites, setInvites] = useState<Invitation[]>([
    { email: '', role: 'Approver' },
    { email: '', role: 'Viewer' },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function updateInvite(index: number, next: Invitation) {
    setInvites((prev) => prev.map((inv, i) => (i === index ? next : inv)))
  }

  function removeInvite(index: number) {
    setInvites((prev) => prev.filter((_, i) => i !== index))
  }

  function addInvite() {
    if (invites.length >= MAX_INVITES) return
    setInvites((prev) => [...prev, { email: '', role: 'Viewer' }])
  }

  async function handleSubmit() {
    const filled = invites.filter((inv) => inv.email.trim())
    if (!filled.length) {
      onSkip()
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/onboarding/invite-team`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ invitations: filled }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Invite failed. Please try again.')
        return
      }
      onNext()
    } catch {
      setError('Unable to connect to server.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="font-heading font-bold text-[28px] text-brand-text">Who else needs access?</h1>
        <p className="text-xs font-mono text-brand-muted">Invite your team to collaborate.</p>
      </div>
      <div className="space-y-2">
        {invites.map((inv, i) => (
          <InviteRow
            key={i}
            invite={inv}
            onChange={(next) => updateInvite(i, next)}
            onRemove={() => removeInvite(i)}
            showRemove={invites.length > 1}
          />
        ))}
        {invites.length < MAX_INVITES && (
          <button
            type="button"
            onClick={addInvite}
            className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors"
          >
            + Add another
          </button>
        )}
      </div>
      <p className="text-[10px] font-mono text-brand-muted">
        They'll receive an email invite and set their own password.
      </p>
      {error && <p className="text-xs font-mono text-brand-danger">{error}</p>}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={loading}
        className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2.5 text-xs font-mono font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Sending invites…' : 'Send Invites →'}
      </button>
      <button
        type="button"
        onClick={onSkip}
        className="w-full text-xs font-mono text-brand-muted hover:text-brand-text transition-colors py-1"
      >
        Skip for now
      </button>
    </div>
  )
}
