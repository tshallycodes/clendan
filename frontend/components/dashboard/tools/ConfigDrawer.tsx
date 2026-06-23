'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { Select } from '@/components/ui/Select'
import { ToolConfigFields, getDefaultConfig } from './ToolConfigFields'
import type { Tool } from './ToolCard'

interface BankAccount {
  id: string
  name: string
  subtype: string
  source: string
}

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
  const [config, setConfig] = useState<Record<string, unknown>>(() => {
    const defaults = getDefaultConfig(toolType)
    const existing = tool?.config_json as Record<string, unknown> | null
    return existing ? { ...defaults, ...existing } : defaults
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [accountsLoading, setAccountsLoading] = useState(toolType === 'reconciliation')
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>(() => {
    const existing = (tool?.config_json as Record<string, unknown> | null)?.account_ids
    return Array.isArray(existing) ? (existing as string[]) : []
  })

  useEffect(() => {
    if (toolType !== 'reconciliation') return
    async function fetchAccounts() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/v1/reconciliation/accounts`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          setAccounts(json.data?.accounts ?? [])
        }
      } finally {
        setAccountsLoading(false)
      }
    }
    fetchAccounts()
  }, [toolType, getToken])

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      const fullConfig = toolType === 'reconciliation'
        ? { ...config, account_ids: selectedAccountIds }
        : config
      const res = tool
        ? await fetch(`${API}/v1/tools/${tool.id}`, {
            method: 'PATCH',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ autonomy_level: autonomy, config: fullConfig }),
          })
        : await fetch(`${API}/v1/tools`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: toolType, autonomy_level: autonomy, config: fullConfig }),
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

  const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="absolute right-0 top-0 h-screen w-96 bg-brand-surface border-l border-brand-border p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-heading font-semibold text-brand-text text-sm">{formatType(toolType)}</h2>
            <p className="text-[10px] font-mono text-brand-muted mt-0.5">{toolType}</p>
            {tool?.last_configured_by_email && (
              <p className="text-[10px] font-mono text-brand-muted mt-1">
                Last configured by{' '}
                <span className="text-brand-secondary">{tool.last_configured_by_email.split('@')[0]}</span>
              </p>
            )}
          </div>
          <button type="button" onClick={onClose} className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none">✕</button>
        </div>

        <div className="space-y-5">
          <div className="space-y-1.5">
            <label className={labelClass}>Autonomy Level</label>
            <Select
              value={autonomy}
              onChange={setAutonomy}
              options={[
                { value: 'auto', label: 'Auto — executes without approval' },
                { value: 'approve', label: 'Approve — requires human approval above threshold' },
                { value: 'suggest', label: 'Suggest — recommends actions only' },
              ]}
            />
          </div>

          <ToolConfigFields
            toolType={toolType}
            config={config}
            onChange={(key, value) => setConfig(prev => ({ ...prev, [key]: value }))}
          />

          {toolType === 'reconciliation' && (
            <div className="space-y-2">
              <label className={labelClass}>Bank Accounts</label>
              {accountsLoading ? (
                <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-3">
                  <p className="text-[10px] font-mono text-brand-muted">Loading accounts…</p>
                </div>
              ) : accounts.length === 0 ? (
                <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-3">
                  <p className="text-[10px] font-mono text-brand-muted">No bank accounts found. Connect a bank via Integrations first.</p>
                </div>
              ) : (
                <>
                  <p className="text-[10px] font-mono text-brand-muted">Uncheck accounts to exclude them. Leave all checked to reconcile everything.</p>
                  <div className="bg-brand-bg border border-brand-border rounded-sm divide-y divide-brand-border">
                    {accounts.map((a) => {
                      const checked = selectedAccountIds.length === 0 || selectedAccountIds.includes(a.id)
                      return (
                        <label key={a.id} className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-brand-elevated transition-colors">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                const next = [...selectedAccountIds, a.id]
                                setSelectedAccountIds(next.length === accounts.length ? [] : next)
                              } else {
                                const next = (selectedAccountIds.length === 0 ? accounts.map(x => x.id) : selectedAccountIds).filter(id => id !== a.id)
                                setSelectedAccountIds(next)
                              }
                            }}
                            className="accent-[#00C853] w-3.5 h-3.5 shrink-0"
                          />
                          <div className="min-w-0">
                            <p className="text-xs font-mono text-brand-text truncate">{a.name}</p>
                            <p className="text-[10px] font-mono text-brand-muted">{a.source}{a.subtype ? ` · ${a.subtype}` : ''}</p>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                  {selectedAccountIds.length > 0 && selectedAccountIds.length < accounts.length && (
                    <p className="text-[10px] font-mono text-[#f5a623]">
                      {selectedAccountIds.length} of {accounts.length} accounts selected
                    </p>
                  )}
                </>
              )}
            </div>
          )}

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
