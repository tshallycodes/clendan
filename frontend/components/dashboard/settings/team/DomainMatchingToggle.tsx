'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Props {
  initialEnabled: boolean
  domain: string
}

export function DomainMatchingToggle({ initialEnabled, domain }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [enabled, setEnabled] = useState(initialEnabled)
  const [saving, setSaving] = useState(false)

  async function handleToggle() {
    const next = !enabled
    setSaving(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/organisations/me/settings`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain_matching: next }),
      })
      if (!res.ok) { toast('Failed to update domain matching', 'error'); return }
      setEnabled(next)
      toast(next ? 'Domain matching enabled' : 'Domain matching disabled', 'success')
    } catch {
      toast('Failed to update domain matching', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-start justify-between gap-6 bg-brand-surface border border-brand-border rounded-sm p-4">
      <div className="space-y-1">
        <p className="text-xs font-mono text-brand-text">
          Allow anyone with a <span className="text-brand-green">@{domain}</span> Google account to join automatically
        </p>
        <p className="text-[10px] font-mono text-[#f5a623]">
          Warning: only enable this for your company domain
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        disabled={saving}
        onClick={handleToggle}
        className={`relative shrink-0 w-9 h-5 rounded-full transition-colors disabled:opacity-40 ${enabled ? 'bg-brand-green' : 'bg-brand-border'}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0'}`}
        />
      </button>
    </div>
  )
}
