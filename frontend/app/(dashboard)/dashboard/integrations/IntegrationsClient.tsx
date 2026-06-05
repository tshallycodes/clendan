'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useRouter } from 'next/navigation'
import { StatusBadge } from '@/components/dashboard/StatusBadge'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

const AVAILABLE = [
  { name: 'QuickBooks', category: 'Accounting', desc: 'Full AP/AR sync', connectType: 'oauth' as const, available: true },
  { name: 'Xero', category: 'Accounting', desc: 'Bills, invoices, payments', connectType: 'oauth' as const, available: false },
  { name: 'FreshBooks', category: 'Accounting', desc: 'Invoice and payment sync', connectType: 'oauth' as const, available: false },
  { name: 'Plaid', category: 'Banking', desc: 'Bank feeds and transactions', connectType: 'plaid_link' as const, available: true },
  { name: 'TrueLayer', category: 'Banking', desc: 'Open banking (UK/EU)', connectType: 'oauth' as const, available: false },
  { name: 'Stripe', category: 'Payments', desc: 'Revenue and charges', connectType: 'oauth' as const, available: false },
  { name: 'GoCardless', category: 'Payments', desc: 'Direct debit', connectType: 'oauth' as const, available: false },
  { name: 'NetSuite', category: 'ERP', desc: 'Full ERP sync', connectType: 'oauth' as const, available: false },
]

interface Props {
  qbStatus: string
  plaidStatus: string
  plaidAccounts: number
  plaidTransactions: number
}

interface ConnectedIntegration {
  name: string
  description: string
  status: string
  summary: string
  disconnectPath: string
}

export function IntegrationsClient({ qbStatus, plaidStatus, plaidAccounts, plaidTransactions }: Props) {
  const { getToken } = useAuth()
  const router = useRouter()
  const [confirming, setConfirming] = useState<string | null>(null)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)

  const connected: ConnectedIntegration[] = []
  if (qbStatus === 'connected') {
    connected.push({ name: 'QuickBooks', description: 'Full AP/AR sync', status: 'connected', summary: '', disconnectPath: '/v1/integrations/quickbooks/disconnect' })
  }
  if (plaidStatus === 'connected') {
    connected.push({ name: 'Plaid', description: 'Bank feeds and transactions', status: 'connected', summary: `${plaidAccounts} accounts · ${plaidTransactions} transactions`, disconnectPath: '/v1/integrations/plaid/disconnect' })
  }

  async function handleDisconnect(intg: ConnectedIntegration) {
    if (confirming !== intg.name) {
      setConfirming(intg.name)
      return
    }
    setDisconnecting(intg.name)
    try {
      const token = await getToken()
      await fetch(`${API}${intg.disconnectPath}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
      router.refresh()
    } finally {
      setDisconnecting(null)
      setConfirming(null)
    }
  }

  async function handleConnect(name: string, connectType: string) {
    if (connectType === 'plaid_link') {
      alert('Coming soon — use Plaid Link widget')
      return
    }
    const token = await getToken()
    const res = await fetch(`${API}/v1/integrations/quickbooks/connect`, { headers: { Authorization: `Bearer ${token}` } })
    if (res.ok) {
      const json = await res.json()
      window.location.href = json.data?.url ?? json.url
    }
  }

  const categories = Array.from(new Set(AVAILABLE.map((i) => i.category)))
  const connectedNames = new Set(connected.map((c) => c.name))
  const availableToShow = AVAILABLE.filter((i) => !connectedNames.has(i.name))

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Integrations</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Connect your financial systems</p>
      </div>

      {connected.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
            Connected
          </h2>
          {connected.map((intg) => (
            <div key={intg.name} className="bg-brand-surface border border-brand-border border-l-[3px] border-l-brand-green rounded-sm p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-brand-text font-medium">{intg.name}</span>
                    <StatusBadge status="connected" />
                  </div>
                  <p className="text-xs font-mono text-brand-muted">{intg.description}</p>
                  <p className="text-[10px] font-mono text-brand-secondary">Last synced: just now</p>
                  {intg.summary && <p className="text-[10px] font-mono text-brand-muted">{intg.summary}</p>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="relative group">
                    <button
                      disabled
                      className="text-xs font-mono border border-brand-border text-brand-muted rounded-sm px-3 py-1.5 disabled:opacity-40 cursor-not-allowed"
                    >
                      Resync
                    </button>
                    <span className="absolute bottom-full right-0 mb-1 hidden group-hover:block text-[10px] font-mono text-brand-muted bg-brand-elevated border border-brand-border rounded-sm px-2 py-1 whitespace-nowrap">
                      Manual sync coming soon
                    </span>
                  </div>
                  {confirming === intg.name ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-brand-danger">Disconnect from {intg.name}?</span>
                      <button
                        onClick={() => handleDisconnect(intg)}
                        disabled={disconnecting === intg.name}
                        className="text-[10px] font-mono bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] rounded-sm px-2 py-1 hover:bg-[rgba(255,77,109,0.2)] transition-colors disabled:opacity-50"
                      >
                        {disconnecting === intg.name ? 'Disconnecting…' : 'Confirm'}
                      </button>
                      <button
                        onClick={() => setConfirming(null)}
                        className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleDisconnect(intg)}
                      className="text-xs font-mono bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] rounded-sm px-3 py-1.5 hover:bg-[rgba(255,77,109,0.2)] transition-colors"
                    >
                      Disconnect
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </section>
      )}

      <section className="space-y-6">
        <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
          Available Integrations
        </h2>
        {categories.map((cat) => {
          const items = availableToShow.filter((i) => i.category === cat)
          if (items.length === 0) return null
          return (
            <div key={cat} className="space-y-3">
              <h3 className="text-[10px] font-mono uppercase tracking-widest text-brand-secondary">{cat}</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {items.map((intg) => (
                  <div key={intg.name} className="bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3">
                    <div>
                      <div className="text-sm font-mono text-brand-text font-medium">{intg.name}</div>
                      <div className="text-xs font-mono text-brand-muted mt-0.5">{intg.desc}</div>
                    </div>
                    {intg.available ? (
                      <button
                        onClick={() => handleConnect(intg.name, intg.connectType)}
                        className="self-start bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 text-xs font-mono font-medium transition-all"
                      >
                        Connect
                      </button>
                    ) : (
                      <span className="self-start text-[10px] font-mono text-brand-muted border border-brand-border rounded-sm px-2 py-0.5">
                        Coming soon
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </section>
    </div>
  )
}
