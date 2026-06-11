'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import type { Worker } from './WorkerCard'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

function formatType(type: string): string {
  return type.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') + ' Worker'
}

interface Props {
  worker: Worker
  onClose: () => void
  onSaved: () => void
}

export function ConfigDrawer({ worker, onClose, onSaved }: Props) {
  const { getToken } = useAuth()
  const [autonomy, setAutonomy] = useState<Worker['autonomy_level']>(worker.autonomy_level)
  const [autoThreshold, setAutoThreshold] = useState(50000)
  const [approveThreshold, setApproveThreshold] = useState(500000)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/workers/${worker.id}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          autonomy_level: autonomy,
          config: { policy: { auto_threshold: autoThreshold, approve_threshold: approveThreshold } },
        }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Failed to save changes.')
        return
      }
      setSaved(true)
      setTimeout(() => { setSaved(false); onSaved() }, 1000)
    } catch {
      setError('Unable to connect to server.')
    } finally {
      setSaving(false)
    }
  }

  const inputClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text outline-none transition-colors'
  const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-[rgba(0,0,0,0.5)]" onClick={onClose} />
      <div className="absolute right-0 top-0 h-screen w-96 bg-brand-surface border-l border-brand-border p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-heading font-semibold text-brand-text text-sm">{formatType(worker.type)}</h2>
            <p className="text-[10px] font-mono text-brand-muted mt-0.5">{worker.type}</p>
          </div>
          <button type="button" onClick={onClose} className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none">✕</button>
        </div>

        <div className="space-y-5">
          <div className="space-y-1.5">
            <label className={labelClass}>Autonomy Level</label>
            <select
              value={autonomy}
              onChange={(e) => setAutonomy(e.target.value as Worker['autonomy_level'])}
              className={inputClass}
            >
              <option value="auto">Auto — executes without approval</option>
              <option value="approve">Approve — requires human approval above threshold</option>
              <option value="suggest">Suggest — recommends actions only</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className={labelClass}>Auto Threshold</label>
            <input
              type="number"
              min={0}
              value={autoThreshold}
              onChange={(e) => setAutoThreshold(Number(e.target.value))}
              className={inputClass}
            />
            <p className="text-[10px] font-mono text-brand-muted">£{(autoThreshold / 100).toFixed(2)} — stored as pence</p>
          </div>

          <div className="space-y-1.5">
            <label className={labelClass}>Approve Threshold</label>
            <input
              type="number"
              min={0}
              value={approveThreshold}
              onChange={(e) => setApproveThreshold(Number(e.target.value))}
              className={inputClass}
            />
            <p className="text-[10px] font-mono text-brand-muted">£{(approveThreshold / 100).toFixed(2)} — stored as pence</p>
          </div>

          {error && <p className="text-xs font-mono text-[#ff4d6d]">{error}</p>}

          <button
            type="button"
            onClick={handleSave}
            disabled={saving || saved}
            className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-mono font-medium transition-all disabled:opacity-50"
          >
            {saved ? 'Saved ✓' : saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}
