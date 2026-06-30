'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Member {
  id: string
  email: string
  role: string
}

const ROLE_COLORS: Record<string, string> = {
  owner:    'text-brand-green border-brand-green/30 bg-[rgba(0,200,83,0.08)]',
  admin:    'text-[#00a8cc] border-[#00a8cc]/30 bg-[rgba(0,168,204,0.08)]',
  approver: 'text-[#f5a623] border-[#f5a623]/30 bg-[rgba(245,166,35,0.08)]',
  viewer:   'text-brand-muted border-brand-border bg-transparent',
  member:   'text-brand-muted border-brand-border bg-transparent',
}

function nameFromEmail(email: string): string {
  const local = email.split('@')[0]
  return local
    .split(/[._\-+]/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()
}

export function TeamSection() {
  const { getToken } = useAuth()
  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/tenants/me/members`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const j = await res.json()
          setMembers(j.data.members)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [getToken])

  if (loading) {
    return (
      <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
        {[0, 1].map((i) => (
          <div key={i} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
            <div className="w-24 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
            <div className="flex-1 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
            <div className="w-14 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
          </div>
        ))}
      </div>
    )
  }

  if (members.length === 0) {
    return <p className="text-xs font-body text-brand-muted">No members found.</p>
  }

  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      {members.map((m) => (
        <div key={m.id} className="bg-brand-surface px-4 py-3 flex items-center gap-3">
          <span className="w-32 shrink-0 text-xs font-body text-brand-text truncate">
            {m.email ? nameFromEmail(m.email) : <span className="text-brand-muted">—</span>}
          </span>
          <span className="flex-1 text-xs font-body text-brand-muted truncate">
            {m.email || <span className="text-brand-muted italic">no email</span>}
          </span>
          <span className={`shrink-0 text-[11px] font-body px-2 py-0.5 rounded-sm border ${ROLE_COLORS[m.role.toLowerCase()] ?? ROLE_COLORS.member}`}>
            {capitalize(m.role)}
          </span>
        </div>
      ))}
    </div>
  )
}
