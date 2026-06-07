'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { ROLE_COLORS, ROLE_LABEL, type Member } from './types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

const ASSIGNABLE_ROLES = ['org:admin', 'org:approver', 'org:viewer'] as const
type AssignableRole = (typeof ASSIGNABLE_ROLES)[number]

interface Props {
  members: Member[]
  onChanged: () => void
}

export function MembersTable({ members, onChanged }: Props) {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const [loadingId, setLoadingId] = useState<string | null>(null)

  async function handleRoleChange(id: string, role: AssignableRole) {
    setLoadingId(id)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/organisations/me/members/${id}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role }),
      })
      onChanged()
    } finally {
      setLoadingId(null)
    }
  }

  async function handleRemove(id: string) {
    setLoadingId(id)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/organisations/me/members/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      onChanged()
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      <div className="bg-brand-bg px-4 py-2 grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center">
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Email</span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Role</span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Joined</span>
        {canConfigure && <span className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Actions</span>}
      </div>
      {members.map((m) => {
        const isOwner = m.role === 'org:owner'
        const busy = loadingId === m.id
        return (
          <div key={m.id} className="bg-brand-surface px-4 py-3 grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center">
            <span className="text-xs font-mono text-brand-text truncate">{m.email}</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${ROLE_COLORS[m.role] ?? ROLE_COLORS['org:viewer']}`}>
              {ROLE_LABEL[m.role] ?? m.role}
            </span>
            <span className="text-[10px] font-mono text-brand-muted">
              {new Date(m.joined_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
            </span>
            {canConfigure ? (
              <div className="flex items-center gap-2">
                {!isOwner && !m.is_self && (
                  <>
                    <select
                      disabled={busy}
                      value={m.role}
                      onChange={(e) => handleRoleChange(m.id, e.target.value as AssignableRole)}
                      className="bg-brand-bg border border-brand-border focus:border-brand-green text-brand-text rounded-sm px-2 py-1 text-[10px] font-mono outline-none disabled:opacity-40 transition-colors"
                    >
                      {ASSIGNABLE_ROLES.map((r) => (
                        <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => handleRemove(m.id)}
                      className="text-[10px] font-mono text-brand-danger border border-brand-danger/30 bg-brand-danger/08 hover:bg-brand-danger/15 rounded-sm px-2 py-0.5 transition-colors disabled:opacity-40"
                    >
                      {busy ? '…' : 'Remove'}
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
