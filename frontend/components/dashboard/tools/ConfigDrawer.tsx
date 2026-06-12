'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { ToolConfigFields, getDefaultConfig } from './ToolConfigFields'
import type { Tool } from './ToolCard'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function formatType(type: string): string {
  return type.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

interface Props {
  tool: Tool | null
  toolType: string
  onClose: () => void
  onSaved: () => void
}

export function ConfigDrawer({ tool, toolType, onClose, onSaved }: Props) {
  const { getToken } = useAuth()
  const [autonomy, setAutonomy] = useState<string>(tool?.autonomy_level ?? 'approve')
  const [config, setConfig] = useState<Record<string, unknown>>(getDefaultConfig(toolType))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      const res = tool
        ? await fetch(`${API}/v1/tools/${tool.id}`, {
            method: 'PATCH',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ autonomy_level: autonomy, config }),
          })
        : await fetch(`${API}/v1/tools`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: toolType, autonomy_level: autonomy, config }),
          })

      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Failed to save.')
        return
      }
      setSaved(true)
      setTimeout(() => { setSaved(false); onSaved() }, 800)
    } catch {
      setError('Unable to connect to server.')
    } finally {
      setSaving(false)
    }
  }

  const inputClass = 'w-full bg-brand-bg border border-brand-border focus:border-[#00C853] rounded-sm px-3 py-2 text-xs font-mono text-brand-text outline-none transition-colors'
  const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-[rgba(0,0,0,0.5)]" onClick={onClose} />
      <div className="absolute right-0 top-0 h-screen w-96 bg-brand-surface border-l border-brand-border p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-heading font-semibold text-brand-text text-sm">{formatType(toolType)}</h2>
            <p className="text-[10px] font-mono text-brand-muted mt-0.5">{toolType}</p>
          </div>
          <button type="button" onClick={onClose} className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none">✕</button>
        </div>

        <div className="space-y-5">
          <div className="space-y-1.5">
            <label className={labelClass}>Autonomy Level</label>
            <select value={autonomy} onChange={(e) => setAutonomy(e.target.value)} className={inputClass}>
              <option value="auto">Auto — executes without approval</option>
              <option value="approve">Approve — requires human approval above threshold</option>
              <option value="suggest">Suggest — recommends actions only</option>
            </select>
          </div>

          <ToolConfigFields
            toolType={toolType}
            config={config}
            onChange={(key, value) => setConfig(prev => ({ ...prev, [key]: value }))}
          />

          {error && <p className="text-xs font-mono text-[#ff4d6d]">{error}</p>}

          <button
            type="button"
            onClick={handleSave}
            disabled={saving || saved}
            className="w-full bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-mono font-medium transition-all disabled:opacity-50"
          >
            {saved ? 'Saved ✓' : saving ? 'Saving…' : tool ? 'Save Changes' : 'Deploy Tool'}
          </button>
        </div>
      </div>
    </div>
  )
}
