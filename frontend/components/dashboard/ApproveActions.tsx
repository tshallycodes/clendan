'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useToast } from '@/components/Providers'

interface Props {
  approvalId: string
  token: string
}

export function ApproveActions({ approvalId, token }: Props) {
  const router = useRouter()
  const { toast } = useToast()
  const [loading, setLoading] = useState<'approve' | 'reject' | null>(null)

  async function respond(action: 'approve' | 'reject') {
    setLoading(action)
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/approvals/${approvalId}/respond`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ action }),
        }
      )
      if (res.ok) {
        toast(action === 'approve' ? 'Approved' : 'Rejected', action === 'approve' ? 'success' : 'info')
        router.refresh()
      } else {
        toast('Action failed — try again', 'error')
      }
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="flex gap-2">
      <button
        onClick={() => respond('approve')}
        disabled={!!loading}
        className="text-[10px] font-body px-3 py-1 border border-[rgba(0,200,83,0.3)] text-brand-green hover:bg-[rgba(0,200,83,0.08)] transition-colors rounded-sm disabled:opacity-40"
      >
        {loading === 'approve' ? '...' : 'APPROVE'}
      </button>
      <button
        onClick={() => respond('reject')}
        disabled={!!loading}
        className="text-[10px] font-body px-3 py-1 border border-[rgba(255,77,109,0.3)] text-brand-danger hover:bg-[rgba(255,77,109,0.08)] transition-colors rounded-sm disabled:opacity-40"
      >
        {loading === 'reject' ? '...' : 'REJECT'}
      </button>
    </div>
  )
}
