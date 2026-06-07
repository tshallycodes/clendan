'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface Member {
  id: string
  email: string
  role: string
}

const ROLE_COLORS: Record<string, string> = {
  owner: 'text-brand-green border-brand-green/30 bg-brand-green/08',
  admin: 'text-[#00a8cc] border-[#00a8cc]/30 bg-[#00a8cc]/08',
  member: 'text-brand-muted border-brand-border',
}

export function TeamSection() {
  const { getToken } = useAuth()
  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/v1/tenants/me/members`, {
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
  }, [])

  if (loading) {
    return (
      <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
        {[0, 1].map((i) => (
          <div key={i} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
            <div className="flex-1 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
            <div className="w-12 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
          </div>
        ))}
      </div>
    )
  }

  if (members.length === 0) {
    return <p className="text-xs font-mono text-brand-muted">No members found.</p>
  }

  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      {members.map((m) => (
        <div key={m.id} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
          <span className="flex-1 text-xs font-mono text-brand-text">{m.email}</span>
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${ROLE_COLORS[m.role] ?? ROLE_COLORS.member}`}>
            {m.role}
          </span>
        </div>
      ))}
    </div>
  )
}
