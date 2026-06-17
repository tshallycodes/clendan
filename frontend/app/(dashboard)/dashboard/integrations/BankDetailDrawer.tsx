'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import Image from 'next/image'
import { BankDef } from './banks-data'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Account {
  id: string
  name: string
  type: string
  subtype: string
  current_balance_minor: number
  currency: string
}

interface Transaction {
  id: string
  merchant_name: string | null
  description: string
  amount_minor: number
  currency: string
  date: string
  ai_category: string | null
}

interface BankConnection {
  integration_id: string
  institution_name: string | null
  status: string
  connected_at: string | null
  last_synced_at: string | null
  accounts: Account[]
  recent_transactions: Transaction[]
}

interface Props {
  bank: BankDef | null
  onClose: () => void
  onConnect: (bank: BankDef) => void
  onDisconnect: (integrationId: string, provider: string) => Promise<void>
  onResync: (integrationId: string, provider: string) => Promise<void>
  onSyncLog: (slug: string, name: string) => void
}

function fmt(minor: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency, minimumFractionDigits: 2 }).format(minor / 100)
  } catch {
    return `${(minor / 100).toFixed(2)}`
  }
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; border: string }> = {
    connected: { bg: 'rgba(0,200,83,0.08)', color: '#00C853', border: 'rgba(0,200,83,0.2)' },
    syncing:   { bg: 'rgba(0,168,204,0.08)', color: '#00a8cc', border: 'rgba(0,168,204,0.2)' },
    error:     { bg: 'rgba(255,77,109,0.08)', color: '#ff4d6d', border: 'rgba(255,77,109,0.2)' },
  }
  const s = map[status] ?? { bg: 'rgba(82,196,120,0.1)', color: 'var(--brand-muted)', border: 'rgba(82,196,120,0.25)' }
  return (
    <span
      className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm"
      style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}
    >
      {status}
    </span>
  )
}

function ConnectionSection({
  conn,
  provider,
  onDisconnect,
  onResync,
  onSyncLog,
}: {
  conn: BankConnection
  provider: string
  onDisconnect: (integrationId: string, provider: string) => Promise<void>
  onResync: (integrationId: string, provider: string) => Promise<void>
  onSyncLog: (slug: string, name: string) => void
}) {
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [resyncing, setResyncing] = useState(false)

  const lastSyncDisplay = conn.last_synced_at
    ? new Date(conn.last_synced_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : 'Not synced'

  return (
    <div className="bg-brand-elevated border border-brand-border rounded-sm overflow-hidden" style={{ borderLeft: '3px solid #00C853' }}>
      {/* Header row */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-brand-border">
        <div>
          <p className="text-xs font-mono text-brand-text">{conn.institution_name || 'Connected Account'}</p>
          <p className="text-[10px] font-mono text-brand-muted mt-0.5">Last sync: {lastSyncDisplay}</p>
        </div>
        <StatusBadge status={conn.status} />
      </div>

      {/* Accounts */}
      {conn.accounts.length > 0 && (
        <div className="divide-y divide-brand-border border-b border-brand-border">
          {conn.accounts.map((a) => (
            <div key={a.id} className="flex items-center justify-between gap-4 px-4 py-2.5">
              <div className="min-w-0">
                <p className="text-xs font-mono text-brand-text truncate">{a.name}</p>
                <p className="text-[10px] font-mono text-brand-muted uppercase mt-0.5">{a.subtype || a.type}</p>
              </div>
              <p className="text-xs font-mono text-brand-text shrink-0">{fmt(a.current_balance_minor, a.currency)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Recent transactions */}
      {conn.recent_transactions.length > 0 && (
        <div className="border-b border-brand-border">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted px-4 pt-3 pb-2">Recent</p>
          <div className="divide-y divide-brand-border">
            {conn.recent_transactions.slice(0, 3).map((t) => (
              <div key={t.id} className="flex items-center justify-between gap-4 px-4 py-2">
                <p className="text-[10px] font-mono text-brand-secondary truncate">{t.merchant_name || t.description}</p>
                <div className="text-right shrink-0">
                  <p className="text-[10px] font-mono text-brand-text">{fmt(t.amount_minor, t.currency)}</p>
                  <p className="text-[10px] font-mono text-brand-muted">
                    {new Date(t.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-4 py-3 flex gap-2">
        <button
          disabled={resyncing}
          onClick={async () => {
            setResyncing(true)
            try { await onResync(conn.integration_id, provider) } finally { setResyncing(false) }
          }}
          className="flex-1 py-1.5 text-[10px] font-mono text-brand-text bg-transparent border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors disabled:opacity-60"
        >
          {resyncing ? 'Syncing...' : 'Resync'}
        </button>
        <button
          onClick={() => onSyncLog(
            `${provider}/connections/${conn.integration_id}`,
            conn.institution_name || 'Connection',
          )}
          className="flex-1 py-1.5 text-[10px] font-mono text-brand-text bg-transparent border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors"
        >
          Sync Log
        </button>
        {confirmDisconnect ? (
          <>
            <button
              disabled={disconnecting}
              onClick={async () => {
                setDisconnecting(true)
                try { await onDisconnect(conn.integration_id, provider) } finally {
                  setDisconnecting(false)
                  setConfirmDisconnect(false)
                }
              }}
              className="flex-1 py-1.5 text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] rounded-sm hover:bg-[rgba(255,77,109,0.15)] transition-colors disabled:opacity-60"
            >
              {disconnecting ? 'Disconnecting...' : 'Confirm'}
            </button>
            <button
              onClick={() => setConfirmDisconnect(false)}
              className="px-3 py-1.5 text-[10px] font-mono text-brand-muted bg-transparent border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            onClick={() => setConfirmDisconnect(true)}
            className="flex-1 py-1.5 text-[10px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d]/30 rounded-sm hover:bg-[rgba(255,77,109,0.15)] transition-colors"
          >
            Disconnect
          </button>
        )}
      </div>
    </div>
  )
}

export function BankDetailDrawer({ bank, onClose, onConnect, onDisconnect, onResync, onSyncLog }: Props) {
  const { getToken } = useAuth()
  const [connections, setConnections] = useState<BankConnection[]>([])
  const [loading, setLoading] = useState(false)
  const [logoError, setLogoError] = useState(false)

  const fetchConnections = useCallback(async (bankDef: BankDef) => {
    setLoading(true)
    try {
      const token = await getToken()
      const param = `institution_name=${encodeURIComponent(bankDef.name)}`
      const res = await fetch(`${API}/v1/integrations/${bankDef.provider}/connections?${param}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const json = await res.json()
        setConnections(json.data?.connections ?? [])
      }
    } catch { /* silent */ } finally { setLoading(false) }
  }, [getToken]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setLogoError(false)
    setConnections([])
    if (!bank) return
    fetchConnections(bank)
  }, [bank?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleDisconnect = async (integrationId: string, provider: string) => {
    await onDisconnect(integrationId, provider)
    if (bank) fetchConnections(bank)
  }

  return (
    <AnimatePresence>
      {bank && (
        <>
          <motion.div
            key="bank-bd"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40"
            onClick={onClose}
          />
          <motion.aside
            key="bank-dr"
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.25 }}
            className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-brand-surface border-l border-brand-border z-50 flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-sm overflow-hidden flex items-center justify-center shrink-0"
                  style={{ backgroundColor: logoError || !bank.domain ? bank.color : 'white' }}
                >
                  {logoError || !bank.domain ? (
                    <span className="text-[10px] font-mono font-bold text-white leading-none">
                      {bank.abbr.slice(0, 2)}
                    </span>
                  ) : (
                    <Image
                      unoptimized
                      src={`https://www.google.com/s2/favicons?sz=64&domain=${bank.domain}`}
                      alt={bank.name} width={24} height={24} className="object-contain"
                      onError={() => setLogoError(true)}
                    />
                  )}
                </div>
                <h2 className="font-heading font-bold text-base text-brand-text">{bank.name}</h2>
              </div>
              <button
                onClick={onClose}
                className="text-brand-muted hover:text-brand-text transition-colors text-xl leading-none"
              >
                &times;
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              {loading ? (
                <div className="space-y-3">
                  {[1, 2].map((i) => (
                    <div key={i} className="h-32 bg-brand-elevated border border-brand-border rounded-sm animate-pulse opacity-60" />
                  ))}
                </div>
              ) : connections.length > 0 ? (
                <>
                  {connections.length > 1 && (
                    <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
                      {connections.length} Connections
                    </p>
                  )}
                  {connections.map((conn) => (
                    <ConnectionSection
                      key={conn.integration_id}
                      conn={conn}
                      provider={bank.provider}
                      onDisconnect={handleDisconnect}
                      onResync={onResync}
                      onSyncLog={onSyncLog}
                    />
                  ))}
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 gap-5 text-center">
                  <div
                    className="w-14 h-14 rounded-sm overflow-hidden flex items-center justify-center border border-brand-border"
                    style={{ backgroundColor: !bank.domain ? bank.color : 'white' }}
                  >
                    {!bank.domain ? (
                      <span className="text-lg font-mono font-bold text-white">{bank.abbr.slice(0, 2)}</span>
                    ) : (
                      <Image
                        unoptimized
                        src={`https://www.google.com/s2/favicons?sz=128&domain=${bank.domain}`}
                        alt={bank.name} width={40} height={40} className="object-contain"
                      />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-mono font-semibold text-brand-text">{bank.name}</p>
                    <p className="text-[10px] font-mono text-brand-muted mt-1.5 max-w-[220px] mx-auto leading-relaxed">
                      Sync accounts and transactions automatically
                    </p>
                  </div>
                  <button
                    onClick={() => onConnect(bank)}
                    className="px-6 py-2.5 bg-[#00C853] text-black text-xs font-mono font-semibold rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all"
                  >
                    Connect
                  </button>
                </div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

