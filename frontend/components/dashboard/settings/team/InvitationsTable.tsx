'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { useToast } from '@/components/Providers'
import { ROLE_COLORS, ROLE_LABEL, type Invitation } from './types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Props {
  invitations: Invitation[]
  onChanged: () => void
}

export function InvitationsTable({ invitations, onChanged }: Props) {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const { toast } = useToast()
  const [revoking, setRevoking] = useState<string | null>(null)

  async function handleRevoke(id: string) {
    setRevoking(id)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/organisations/me/invitations/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { toast('Failed to revoke invitation', 'error'); return }
      toast('Invitation revoked', 'success')
      onChanged()
    } catch {
      toast('Failed to revoke invitation', 'error')
    } finally {
      setRevoking(null)
    }
  }

  if (invitations.length === 0) {
    return <p className="text-xs font-mono text-brand-muted">No pending invitations.</p>
  }

  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      <div className="bg-brand-bg px-4 py-2 grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center">
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Email</span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Role</span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Sent</span>
        {canConfigure && <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Actions</span>}
      </div>
      {invitations.map((inv) => (
        <div key={inv.id} className="bg-brand-surface px-4 py-3 grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center">
          <span className="text-xs font-mono text-brand-text truncate">{inv.email}</span>
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${ROLE_COLORS[inv.role] ?? ROLE_COLORS['org:viewer']}`}>
            {ROLE_LABEL[inv.role] ?? inv.role}
          </span>
          <span className="text-[10px] font-mono text-brand-muted">
            {new Date(inv.sent_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
          </span>
          {canConfigure ? (
            <button
              type="button"
              disabled={revoking === inv.id}
              onClick={() => handleRevoke(inv.id)}
              className="text-[10px] font-mono text-brand-danger border border-brand-danger/30 bg-brand-danger/08 hover:bg-brand-danger/15 rounded-sm px-2 py-0.5 transition-colors disabled:opacity-40"
            >
              {revoking === inv.id ? '…' : 'Revoke'}
            </button>
          ) : (
            <span />
          )}
        </div>
      ))}
    </div>
  )
}
