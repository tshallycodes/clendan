'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type ConnStatus = 'loading' | 'connected' | 'not_connected' | 'disconnected'

interface PlaidData {
  status: ConnStatus
  connected_at: string | null
  accounts: number
  transactions: number
}

interface QBData {
  status: ConnStatus
  connected_at: string | null
}

function StatusBadge({ status }: { status: ConnStatus }) {
  if (status === 'loading') return <span className="text-[10px] font-mono text-brand-muted">—</span>
  const connected = status === 'connected'
  return (
    <span className={[
      'text-[10px] font-mono px-2 py-0.5 rounded-sm border',
      connected
        ? 'text-brand-green border-brand-green/30 bg-brand-green/08'
        : 'text-brand-muted border-brand-border',
    ].join(' ')}>
      {connected ? 'connected' : 'not connected'}
    </span>
  )
}

export function IntegrationsSection() {
  const { getToken } = useAuth()
  const [plaid, setPlaid] = useState<PlaidData>({
    status: 'loading', connected_at: null, accounts: 0, transactions: 0,
  })
  const [qb, setQB] = useState<QBData>({ status: 'loading', connected_at: null })
  const [qbConnecting, setQBConnecting] = useState(false)
  const [disconnecting, setDisconnecting] = useState<'plaid' | 'quickbooks' | null>(null)

  async function load() {
    try {
      const token = await getToken()
      const h = { Authorization: `Bearer ${token}` }
      const [pr, qbr] = await Promise.all([
        fetch(`${API}/v1/integrations/plaid/status`, { headers: h }),
        fetch(`${API}/v1/integrations/quickbooks/status`, { headers: h }),
      ])
      if (pr.ok) {
        const j = await pr.json()
        setPlaid({
          status: j.data.status,
          connected_at: j.data.connected_at ?? null,
          accounts: j.data.accounts ?? 0,
          transactions: j.data.transactions ?? 0,
        })
      } else {
        setPlaid(p => ({ ...p, status: 'not_connected' }))
      }
      if (qbr.ok) {
        const j = await qbr.json()
        setQB({ status: j.data.status, connected_at: j.data.connected_at ?? null })
      } else {
        setQB(p => ({ ...p, status: 'not_connected' }))
      }
    } catch {
      setPlaid(p => ({ ...p, status: 'not_connected' }))
      setQB(p => ({ ...p, status: 'not_connected' }))
    }
  }

  useEffect(() => { load() }, [])

  async function connectQB() {
    setQBConnecting(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/integrations/quickbooks/connect`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const j = await res.json()
        window.location.href = j.data.auth_url
      }
    } finally {
      setQBConnecting(false)
    }
  }

  async function disconnect(type: 'plaid' | 'quickbooks') {
    setDisconnecting(type)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/integrations/${type}/disconnect`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      await load()
    } finally {
      setDisconnecting(null)
    }
  }

  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      {/* Plaid */}
      <div className="bg-brand-surface px-4 py-4 flex items-start gap-4">
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-brand-text font-medium">Plaid</span>
            <StatusBadge status={plaid.status} />
          </div>
          <p className="text-[10px] font-mono text-brand-muted">Bank account connections and transaction sync</p>
          {plaid.status === 'connected' && (
            <p className="text-[10px] font-mono text-brand-muted">
              {plaid.accounts} account{plaid.accounts !== 1 ? 's' : ''} · {plaid.transactions} transaction{plaid.transactions !== 1 ? 's' : ''}
              {plaid.connected_at ? ` · connected ${new Date(plaid.connected_at).toLocaleDateString('en-GB')}` : ''}
            </p>
          )}
        </div>
        {plaid.status === 'connected' && (
          <button
            onClick={() => disconnect('plaid')}
            disabled={disconnecting === 'plaid'}
            className="shrink-0 text-[10px] font-mono text-brand-danger border border-brand-danger/30 bg-brand-danger/08 hover:bg-brand-danger/15 rounded-sm px-2 py-1 transition-colors disabled:opacity-50"
          >
            {disconnecting === 'plaid' ? 'Disconnecting…' : 'Disconnect'}
          </button>
        )}
      </div>

      {/* QuickBooks */}
      <div className="bg-brand-surface px-4 py-4 flex items-start gap-4">
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-brand-text font-medium">QuickBooks</span>
            <StatusBadge status={qb.status} />
          </div>
          <p className="text-[10px] font-mono text-brand-muted">Accounting sync, invoices, and company data</p>
          {qb.status === 'connected' && qb.connected_at && (
            <p className="text-[10px] font-mono text-brand-muted">
              Connected {new Date(qb.connected_at).toLocaleDateString('en-GB')}
            </p>
          )}
        </div>
        <div className="shrink-0">
          {qb.status === 'connected' ? (
            <button
              onClick={() => disconnect('quickbooks')}
              disabled={disconnecting === 'quickbooks'}
              className="text-[10px] font-mono text-brand-danger border border-brand-danger/30 bg-brand-danger/08 hover:bg-brand-danger/15 rounded-sm px-2 py-1 transition-colors disabled:opacity-50"
            >
              {disconnecting === 'quickbooks' ? 'Disconnecting…' : 'Disconnect'}
            </button>
          ) : qb.status !== 'loading' ? (
            <button
              onClick={connectQB}
              disabled={qbConnecting}
              className="text-[10px] font-mono text-brand-text border border-brand-border hover:bg-brand-surface-elevated rounded-sm px-2 py-1 transition-colors disabled:opacity-50"
            >
              {qbConnecting ? 'Connecting…' : 'Connect'}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
