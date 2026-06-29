'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { ROLE_COLORS, ROLE_LABEL, type Member } from './types'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const ASSIGNABLE_ROLES = ['admin', 'approver', 'viewer'] as const
type AssignableRole = (typeof ASSIGNABLE_ROLES)[number]

function nameFromEmail(email: string): string {
  const local = email.split('@')[0]
  return local
    .split(/[._\-+]/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
}

interface Props {
  members: Member[]
  isCurrentUserOwner: boolean
  onChanged: () => void
}

export function MembersTable({ members, isCurrentUserOwner, onChanged }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [transferConfirmId, setTransferConfirmId] = useState<string | null>(null)

  async function handleRoleChange(id: string, role: AssignableRole) {
    setLoadingId(id)
    try {
      const token = await getToken()
      await fetch(`${API}/organisations/me/members/${id}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role }),
      })
      onChanged()
      toast('Role updated', 'success')
    } catch {
      toast('Failed to update role', 'error')
    } finally {
      setLoadingId(null)
    }
  }

  async function handleRemove(id: string) {
    setLoadingId(id)
    try {
      const token = await getToken()
      await fetch(`${API}/organisations/me/members/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      onChanged()
      toast('Member removed', 'success')
    } catch {
      toast('Failed to remove member', 'error')
    } finally {
      setLoadingId(null)
    }
  }

  async function handleTransferOwnership(id: string) {
    setLoadingId(id)
    setTransferConfirmId(null)
    try {
      const token = await getToken()
      await fetch(`${API}/organisations/me/transfer-ownership`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_owner_id: id }),
      })
      onChanged()
      toast('Ownership transferred', 'success')
    } catch {
      toast('Failed to transfer ownership', 'error')
    } finally {
      setLoadingId(null)
    }
  }

  const canConfigure = isCurrentUserOwner

  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      <div className="bg-brand-bg px-4 py-2 grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 items-center">
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted w-28">Name</span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Email</span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Role</span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Joined</span>
        {canConfigure && <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Actions</span>}
      </div>

      {members.map((m) => {
        const isOwnerRow = m.role === 'owner'
        const busy = loadingId === m.id
        const awaitingConfirm = transferConfirmId === m.id

        return (
          <div key={m.id} className="bg-brand-surface px-4 py-3 grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 items-center">
            <span className="w-28 shrink-0 text-xs font-mono text-brand-text truncate">
              {nameFromEmail(m.email)}
              {m.is_self && <span className="ml-1 text-brand-muted">(you)</span>}
            </span>
            <span className="text-xs font-mono text-brand-muted truncate">{m.email}</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border whitespace-nowrap ${ROLE_COLORS[m.role] ?? ROLE_COLORS.viewer}`}>
              {ROLE_LABEL[m.role] ?? m.role}
            </span>
            <span className="text-[10px] font-mono text-brand-muted whitespace-nowrap">
              {new Date(m.joined_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
            </span>

            {canConfigure ? (
              <div className="flex items-center gap-2 justify-end">
                {!isOwnerRow && !m.is_self && (
                  <>
                    <select
                      aria-label={`Change role for ${m.email}`}
                      disabled={busy}
                      value={m.role}
                      onChange={(e) => handleRoleChange(m.id, e.target.value as AssignableRole)}
                      className="bg-brand-bg border border-brand-border focus:border-brand-green text-brand-text rounded-sm px-2 py-1 text-[10px] font-mono outline-none disabled:opacity-40 transition-colors"
                    >
                      {ASSIGNABLE_ROLES.map((r) => (
                        <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                      ))}
                    </select>

                    {awaitingConfirm ? (
                      <div className="flex items-center gap-1">
                        <span className="text-[10px] font-mono text-brand-muted">Confirm?</span>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleTransferOwnership(m.id)}
                          className="text-[10px] font-mono text-brand-green border border-brand-green/30 bg-[rgba(0,200,83,0.08)] hover:bg-[rgba(0,200,83,0.15)] rounded-sm px-2 py-0.5 transition-colors disabled:opacity-40"
                        >
                          Yes
                        </button>
                        <button
                          type="button"
                          onClick={() => setTransferConfirmId(null)}
                          className="text-[10px] font-mono text-brand-muted border border-brand-border rounded-sm px-2 py-0.5 hover:text-brand-text transition-colors"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setTransferConfirmId(m.id)}
                        className="text-[10px] font-mono text-brand-muted border border-brand-border hover:border-brand-green hover:text-brand-green rounded-sm px-2 py-0.5 transition-colors disabled:opacity-40 whitespace-nowrap"
                      >
                        Make Owner
                      </button>
                    )}

                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => handleRemove(m.id)}
                      className="text-[10px] font-mono text-brand-danger border border-brand-danger/30 bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.15)] rounded-sm px-2 py-0.5 transition-colors disabled:opacity-40"
                    >
                      {busy ? 'â€¦' : 'Remove'}
                    </button>
                  </>
                )}
              </div>
            ) : (
              <span />
            )}
          </div>
        )
      })}
    </div>
  )
}
