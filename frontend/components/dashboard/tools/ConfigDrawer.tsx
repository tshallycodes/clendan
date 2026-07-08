'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { Select } from '@/components/ui/Select'
import { ToolConfigFields, getDefaultConfig } from './ToolConfigFields'
import type { Tool } from './ToolCard'
import { useToast } from '@/components/Providers'
import { WORKFLOWS, TOOLS } from '@/app/(dashboard)/tools/tools-data'

interface BankAccount {
  id: string
  name: string
  subtype: string
  source: string
}

const SOURCE_NAMES: Record<string, string> = {
  xero: 'Xero',
  quickbooks: 'QuickBooks',
  freshbooks: 'FreshBooks',
  sage: 'Sage',
  'sage-intacct': 'Sage Intacct',
  stripe: 'Stripe',
  gocardless: 'GoCardless',
  adyen: 'Adyen',
  wise: 'Wise',
  square: 'Square',
  paypal: 'PayPal',
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

/** Auto-handoff toggle to the next tool in the workflow, if this tool has a downstream edge. */
function WorkflowSection({ toolType }: { toolType: string }) {
  const { getToken } = useAuth()
  const { toast } = useToast()

  const workflow = WORKFLOWS.find((w) => w.toolTypes.includes(toolType))
  const idx = workflow ? workflow.toolTypes.indexOf(toolType) : -1
  const nextType = workflow && idx >= 0 && idx < workflow.toolTypes.length - 1 ? workflow.toolTypes[idx + 1] : null
  const nextName = nextType ? (TOOLS.find((t) => t.type === nextType)?.name ?? 'the next tool') : null

  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (!nextType) return
    let active = true
    ;(async () => {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/workflows/connections`, { headers: { Authorization: `Bearer ${token}` } })
        if (!active) return
        if (res.ok) {
          const conns = ((await res.json()).data?.connections ?? []) as { from_type: string; to_type: string; enabled: boolean }[]
          const c = conns.find((x) => x.from_type === toolType && x.to_type === nextType)
          setEnabled(c ? c.enabled : true)
        } else {
          setEnabled(true)
        }
      } catch {
        if (active) setEnabled(true)
      }
    })()
    return () => { active = false }
  }, [toolType, nextType, getToken])

  if (!nextType) return null

  async function toggle() {
    if (enabled === null || pending) return
    const next = !enabled
    setEnabled(next)
    setPending(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/workflows/connections`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_type: toolType, to_type: nextType, enabled: next }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      toast(next ? `Auto-handoff to ${nextName} on` : `Auto-handoff to ${nextName} off`, 'success')
    } catch {
      setEnabled(!next)
      toast('Could not update connection', 'error')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="space-y-2">
      <label className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Workflow</label>
      <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-body text-brand-text">Auto-handoff to {nextName}</p>
          <p className="text-[11px] font-body text-brand-muted mt-0.5 leading-relaxed">
            When on, a successful run automatically triggers {nextName}.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={!!enabled}
          onClick={toggle}
          disabled={enabled === null || pending}
          className={`relative w-9 h-5 rounded-full transition-colors shrink-0 disabled:opacity-50 ${enabled ? 'bg-[#00C853]' : 'bg-brand-border'}`}
        >
          <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0'}`} />
        </button>
      </div>
    </div>
  )
}

export function ConfigDrawer({ tool, toolType, onClose, onSaved }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [autonomy, setAutonomy] = useState<string>(tool?.autonomy_level ?? 'approve')
  const [config, setConfig] = useState<Record<string, unknown>>(() => {
    const defaults = getDefaultConfig(toolType)
    const existing = tool?.config_json as Record<string, unknown> | null
    return existing ? { ...defaults, ...existing } : defaults
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [accountsLoading, setAccountsLoading] = useState(toolType === 'reconciliation')
  const [accountingSources, setAccountingSources] = useState<string[]>([])
  const [paymentSources, setPaymentSources] = useState<string[]>([])
  const [selectedPaymentSources, setSelectedPaymentSources] = useState<string[]>(() => {
    const existing = (tool?.config_json as Record<string, unknown> | null)?.payment_sources
    return Array.isArray(existing) ? (existing as string[]) : []
  })
  const [connected, setConnected] = useState<{ accounting: string[]; bank: string[] }>({ accounting: [], bank: [] })
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>(() => {
    const existing = (tool?.config_json as Record<string, unknown> | null)?.account_ids
    return Array.isArray(existing) ? (existing as string[]) : []
  })
  const [selectedIntegrationSources, setSelectedIntegrationSources] = useState<string[]>(() => {
    const existing = (tool?.config_json as Record<string, unknown> | null)?.integration_sources
    return Array.isArray(existing) ? (existing as string[]) : []
  })

  useEffect(() => {
    if (toolType !== 'reconciliation') return
    async function fetchReconciliationData() {
      try {
        const token = await getToken()
        const [accountsRes, intRes] = await Promise.all([
          fetch(`${API}/reconciliation/accounts`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API}/reconciliation/integrations`, { headers: { Authorization: `Bearer ${token}` } }),
        ])
        if (accountsRes.ok) {
          const json = await accountsRes.json()
          setAccounts(json.data?.accounts ?? [])
        }
        if (intRes.ok) {
          const json = await intRes.json()
          const acct: string[] = json.data?.accounting_sources ?? []
          const pay: string[] = json.data?.payment_sources ?? []
          setAccountingSources(acct)
          setPaymentSources(pay)
          setSelectedIntegrationSources(prev => prev.length === 0 ? acct : prev)
          setSelectedPaymentSources(prev => prev.length === 0 ? pay : prev)
        }
      } finally {
        setAccountsLoading(false)
      }
    }
    fetchReconciliationData()
  }, [toolType, getToken])

  useEffect(() => {
    if (toolType === 'reconciliation') return
    async function fetchConnected() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/integrations/connected`, { headers: { Authorization: `Bearer ${token}` } })
        if (res.ok) {
          const data = (await res.json()).data ?? {}
          setConnected({ accounting: data.accounting ?? [], bank: data.bank ?? [] })
        }
      } catch { /* multiselects show the empty-state hint until resolved */ }
    }
    fetchConnected()
  }, [toolType, getToken])

  async function handleSave() {
    setSaving(true)
    try {
      const token = await getToken()
      const fullConfig = toolType === 'reconciliation'
        ? { ...config, account_ids: selectedAccountIds, integration_sources: selectedIntegrationSources, payment_sources: selectedPaymentSources }
        : config
      const res = tool
        ? await fetch(`${API}/tools/${tool.id}`, {
            method: 'PATCH',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ autonomy_level: autonomy, config: fullConfig }),
          })
        : await fetch(`${API}/tools`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: toolType, autonomy_level: autonomy, config: fullConfig }),
          })

      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        toast((json as { error?: string }).error ?? 'Failed to save.', 'error')
        return
      }
      setSaved(true)
      toast('Configuration saved', 'success')
      setTimeout(() => { setSaved(false); onSaved() }, 800)
    } catch {
      toast('Unable to connect to server.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const labelClass = 'text-[11px] font-body text-brand-muted uppercase tracking-widest'

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="absolute right-0 top-0 h-screen w-96 bg-brand-surface border-l border-brand-border p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-heading font-semibold text-brand-text text-sm">{formatType(toolType)}</h2>
            {tool && (
              <p className="text-[11px] font-body text-brand-muted mt-1">
                Last configured by{' '}
                <span className="text-brand-secondary">
                  {tool.last_configured_by_email ? tool.last_configured_by_email.split('@')[0] : '-'}
                </span>
              </p>
            )}
          </div>
          <button type="button" onClick={onClose} className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none">✕</button>
        </div>

        <div className="space-y-5">
          <div className={`space-y-1.5 ${toolType === 'document_intelligence' ? 'opacity-40 pointer-events-none' : ''}`}>
            <label className={labelClass}>Autonomy Level</label>
            <Select
              value={autonomy}
              onChange={setAutonomy}
              options={[
                { value: 'auto', label: 'Auto - executes without approval' },
                { value: 'approve', label: 'Approve - requires human approval above threshold' },
              ]}
            />
            {toolType === 'document_intelligence' && (
              <p className="text-[11px] font-body text-brand-muted">Routing is controlled by the confidence threshold below.</p>
            )}
          </div>

          <ToolConfigFields
            toolType={toolType}
            config={config}
            onChange={(key, value) => setConfig(prev => ({ ...prev, [key]: value }))}
            dynamicOptions={toolType === 'reconciliation' ? undefined : {
              accounting_sources: connected.accounting,
              bank_sources: connected.bank,
            }}
          />

          <WorkflowSection toolType={toolType} />

          {toolType === 'reconciliation' && (
            <div className="space-y-2">
              <label className={labelClass}>Bank Accounts</label>
              {accountsLoading ? (
                <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-3">
                  <p className="text-[11px] font-body text-brand-muted">Loading accounts…</p>
                </div>
              ) : accounts.length === 0 ? (
                <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-3">
                  <p className="text-[11px] font-body text-brand-muted">No bank accounts found. Connect a bank via Integrations first.</p>
                </div>
              ) : (
                <>
                  <p className="text-[11px] font-body text-brand-muted">Uncheck accounts to exclude them. Leave all checked to reconcile everything.</p>
                  <div className="bg-brand-bg border border-brand-border rounded-sm divide-y divide-brand-border">
                    {accounts.map((a) => {
                      const checked = selectedAccountIds.length === 0 || selectedAccountIds.includes(a.id)
                      return (
                        <button
                          key={a.id}
                          type="button"
                          onClick={() => {
                            if (!checked) {
                              const next = [...selectedAccountIds, a.id]
                              setSelectedAccountIds(next.length === accounts.length ? [] : next)
                            } else {
                              const next = (selectedAccountIds.length === 0 ? accounts.map(x => x.id) : selectedAccountIds).filter(id => id !== a.id)
                              setSelectedAccountIds(next)
                            }
                          }}
                          className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-brand-elevated transition-colors text-left"
                        >
                          <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 transition-colors ${checked ? 'bg-[#00C853] border-[#00C853]' : 'bg-brand-bg border-brand-border'}`}>
                            {checked && (
                              <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                                <path d="M1 3L3 5L7 1" stroke="black" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            )}
                          </span>
                          <div className="min-w-0">
                            <p className="text-xs font-body text-brand-text truncate">{a.name}</p>
                            <p className="text-[11px] font-body text-brand-muted">{a.source}{a.subtype ? ` · ${a.subtype}` : ''}</p>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                  {selectedAccountIds.length > 0 && selectedAccountIds.length < accounts.length && (
                    <p className="text-[11px] font-body text-[#f5a623]">
                      {selectedAccountIds.length} of {accounts.length} accounts selected
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          {toolType === 'reconciliation' && paymentSources.length > 0 && (
            <div className="space-y-2">
              <label className={labelClass}>Payment Integrations</label>
              <p className="text-[11px] font-body text-brand-muted">Uncheck integrations to exclude their transactions from reconciliation.</p>
              <div className="bg-brand-bg border border-brand-border rounded-sm divide-y divide-brand-border">
                {paymentSources.map((source) => {
                  const checked = selectedPaymentSources.length === 0 || selectedPaymentSources.includes(source)
                  return (
                    <button
                      key={source}
                      type="button"
                      onClick={() => {
                        if (!checked) {
                          const next = [...selectedPaymentSources, source]
                          setSelectedPaymentSources(next.length === paymentSources.length ? [] : next)
                        } else {
                          const next = (selectedPaymentSources.length === 0 ? paymentSources : selectedPaymentSources).filter(s => s !== source)
                          setSelectedPaymentSources(next)
                        }
                      }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-brand-elevated transition-colors text-left"
                    >
                      <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 transition-colors ${checked ? 'bg-[#00C853] border-[#00C853]' : 'bg-brand-bg border-brand-border'}`}>
                        {checked && (
                          <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                            <path d="M1 3L3 5L7 1" stroke="black" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </span>
                      <p className="text-xs font-body text-brand-text">{SOURCE_NAMES[source] ?? source}</p>
                    </button>
                  )
                })}
              </div>
              {selectedPaymentSources.length > 0 && selectedPaymentSources.length < paymentSources.length && (
                <p className="text-[11px] font-body text-[#f5a623]">
                  {selectedPaymentSources.length} of {paymentSources.length} integrations selected
                </p>
              )}
            </div>
          )}

          {toolType === 'reconciliation' && accountingSources.length > 0 && (
            <div className="space-y-2">
              <label className={labelClass}>Accounting Integrations</label>
              <p className="text-[11px] font-body text-brand-muted">Uncheck integrations to exclude their invoices and bills from reconciliation.</p>
              <div className="bg-brand-bg border border-brand-border rounded-sm divide-y divide-brand-border">
                {accountingSources.map((source) => {
                  const checked = selectedIntegrationSources.length === 0 || selectedIntegrationSources.includes(source)
                  return (
                    <button
                      key={source}
                      type="button"
                      onClick={() => {
                        if (!checked) {
                          const next = [...selectedIntegrationSources, source]
                          setSelectedIntegrationSources(next.length === accountingSources.length ? [] : next)
                        } else {
                          const next = (selectedIntegrationSources.length === 0 ? accountingSources : selectedIntegrationSources).filter(s => s !== source)
                          setSelectedIntegrationSources(next)
                        }
                      }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-brand-elevated transition-colors text-left"
                    >
                      <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 transition-colors ${checked ? 'bg-[#00C853] border-[#00C853]' : 'bg-brand-bg border-brand-border'}`}>
                        {checked && (
                          <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                            <path d="M1 3L3 5L7 1" stroke="black" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </span>
                      <p className="text-xs font-body text-brand-text">{SOURCE_NAMES[source] ?? source}</p>
                    </button>
                  )
                })}
              </div>
              {selectedIntegrationSources.length > 0 && selectedIntegrationSources.length < accountingSources.length && (
                <p className="text-[11px] font-body text-[#f5a623]">
                  {selectedIntegrationSources.length} of {accountingSources.length} integrations selected
                </p>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={handleSave}
            disabled={saving || saved}
            className="w-full bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-body font-medium transition-all disabled:opacity-50"
          >
            {saved ? 'Saved ✓' : saving ? 'Saving…' : tool ? 'Save Changes' : 'Deploy Tool'}
          </button>
        </div>
      </div>
    </div>
  )
}
