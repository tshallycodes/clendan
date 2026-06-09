'use client'

import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure, useIsOwner } from '@/lib/auth-client'
import { MembersTable } from './MembersTable'
import { InvitationsTable } from './InvitationsTable'
import { InviteForm } from './InviteForm'
import { DomainMatchingToggle } from './DomainMatchingToggle'
import { InviteLinksSection } from './InviteLinksSection'
import type { Member, Invitation } from './types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface OrgSettings {
  domain: string
  domain_matching: boolean
}

function SectionSkeleton() {
  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      {[0, 1, 2].map((i) => (
        <div key={i} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
          <div className="flex-1 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
          <div className="w-16 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
          <div className="w-20 h-3 bg-brand-surface-elevated rounded-sm animate-pulse" />
        </div>
      ))}
    </div>
  )
}

export function TeamPageClient() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const isOwner = useIsOwner()

  const [members, setMembers] = useState<Member[]>([])
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [settings, setSettings] = useState<OrgSettings | null>(null)
  const [loadingMembers, setLoadingMembers] = useState(true)
  const [loadingInvites, setLoadingInvites] = useState(true)

  const fetchMembers = useCallback(async () => {
    setLoadingMembers(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/organisations/me/members`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const json = await res.json()
        setMembers((json.data?.members ?? json.data ?? []) as Member[])
      }
    } finally {
      setLoadingMembers(false)
    }
  }, [getToken])

  const fetchInvitations = useCallback(async () => {
    setLoadingInvites(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/organisations/me/invitations`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const json = await res.json()
        setInvitations((json.data?.invitations ?? json.data ?? []) as Invitation[])
      }
    } finally {
      setLoadingInvites(false)
    }
  }, [getToken])

  useEffect(() => {
    fetchMembers()
    fetchInvitations()

    async function fetchSettings() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/v1/organisations/me/settings`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          setSettings((json.data ?? json) as OrgSettings)
        }
      } catch {
        // settings unavailable — hide domain toggle
      }
    }
    fetchSettings()
  }, [fetchMembers, fetchInvitations, getToken])

  return (
    <div className="p-6 max-w-3xl space-y-10">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Team</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Manage members, roles, and invitations</p>
      </div>

      <section className="space-y-4">
        <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
          Members
        </h2>
        {loadingMembers ? (
          <SectionSkeleton />
        ) : members.length === 0 ? (
          <p className="text-xs font-mono text-brand-muted">No members found.</p>
        ) : (
          <MembersTable members={members} isCurrentUserOwner={isOwner} onChanged={fetchMembers} />
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
          Pending Invitations
        </h2>
        {loadingInvites ? (
          <SectionSkeleton />
        ) : (
          <InvitationsTable invitations={invitations} onChanged={fetchInvitations} />
        )}
      </section>

      {canConfigure && (
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
            Invite Team Member
          </h2>
          <InviteForm onInvited={fetchInvitations} />
        </section>
      )}

      {canConfigure && (
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
            Invite Links
          </h2>
          <InviteLinksSection />
        </section>
      )}

      {isOwner && settings && (
        <section className="space-y-4">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
            Google SSO Domain Matching
          </h2>
          <DomainMatchingToggle
            initialEnabled={settings.domain_matching}
            domain={settings.domain}
          />
        </section>
      )}
    </div>
  )
}
