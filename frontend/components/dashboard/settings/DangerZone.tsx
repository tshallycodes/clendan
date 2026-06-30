'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useIsOwner } from '@/lib/auth-client'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function DangerZone() {
  const { getToken } = useAuth()
  const isOwner = useIsOwner()
  const [pauseConfirm, setPauseConfirm] = useState(false)
  const [pausing, setPausing] = useState(false)
  const [pauseDone, setPauseDone] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleteInput, setDeleteInput] = useState('')
  const { toast } = useToast()

  async function handlePauseAll() {
    if (!pauseConfirm) { setPauseConfirm(true); return }
    setPausing(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/tools`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) {
        const json = await res.json()
        const tools: { id: string }[] = json.data ?? json ?? []
        await Promise.all(
          tools.map((w) =>
            fetch(`${API}/tools/${w.id}`, {
              method: 'PATCH',
              headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({ status: 'inactive' }),
            })
          )
        )
      }
      setPauseDone(true)
      setPauseConfirm(false)
      setTimeout(() => setPauseDone(false), 3000)
      toast('All tools paused', 'success')
    } catch {
      toast('Failed to pause tools', 'error')
    } finally {
      setPausing(false)
    }
  }

  if (!isOwner) {
    return (
      <p className="text-xs font-body text-brand-muted">Only the organisation owner can access danger zone actions.</p>
    )
  }

  return (
    <div className="border-l-[3px] border-l-[#ff4d6d] pl-4 space-y-6">
      <div className="space-y-3">
        <div>
          <p className="text-xs font-body text-brand-text font-medium">Pause all tools</p>
          <p className="text-[10px] font-body text-brand-muted mt-0.5">Sets all active tools to inactive. They can be resumed individually.</p>
        </div>
        {pauseConfirm && (
          <p className="text-[10px] font-body text-[#ff4d6d]">This will pause all active tools. Click again to confirm.</p>
        )}
        {pauseDone && (
          <p className="text-[10px] font-body text-brand-green">All tools paused.</p>
        )}
        <button
          type="button"
          onClick={handlePauseAll}
          disabled={pausing}
          className="text-xs font-body bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] hover:bg-[rgba(255,77,109,0.2)] rounded-sm px-3 py-1.5 transition-colors disabled:opacity-50"
        >
          {pausing ? 'Pausing…' : pauseConfirm ? 'Confirm pause' : 'Pause all tools'}
        </button>
        {pauseConfirm && (
          <button
            type="button"
            onClick={() => setPauseConfirm(false)}
            className="ml-2 text-[10px] font-body text-brand-muted hover:text-brand-text transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      <div className="space-y-3">
        <div>
          <p className="text-xs font-body text-brand-text font-medium">Delete account</p>
          <p className="text-[10px] font-body text-brand-muted mt-0.5">Permanently removes your organisation and all data. This cannot be undone.</p>
        </div>
        {!deleteConfirm ? (
          <button
            type="button"
            onClick={() => setDeleteConfirm(true)}
            className="text-xs font-body bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] hover:bg-[rgba(255,77,109,0.2)] rounded-sm px-3 py-1.5 transition-colors"
          >
            Delete account
          </button>
        ) : (
          <div className="space-y-3">
            <p className="text-[10px] font-body text-[#ff4d6d]">This action is permanent. Type DELETE to confirm.</p>
            <input
              type="text"
              value={deleteInput}
              onChange={(e) => setDeleteInput(e.target.value)}
              placeholder="DELETE"
              className="w-full max-w-xs bg-brand-bg border border-[#ff4d6d]/40 focus:border-[#ff4d6d] rounded-sm px-3 py-2 text-xs font-body text-brand-text placeholder:text-brand-muted outline-none transition-colors"
            />
            {deleteInput === 'DELETE' && (
              <p className="text-[10px] font-body text-brand-muted">
                To delete your account, contact{' '}
                <a href="mailto:support@clendan.com" className="text-[#ff4d6d] hover:underline">support@clendan.com</a>
              </p>
            )}
            <button
              type="button"
              onClick={() => { setDeleteConfirm(false); setDeleteInput('') }}
              className="text-[10px] font-body text-brand-muted hover:text-brand-text transition-colors"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
