'use client'

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import Image from 'next/image'
import { BankDef } from './banks-data'
import { IntegrationStatus } from './types'
import { StatusDot, StatusLabel } from './CardStatusIndicator'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

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

interface Props {
  bank: BankDef | null
  plaidStatus: IntegrationStatus
  connectedInstitutionId: string | null
  onClose: () => void
  onConnect: (bank: BankDef) => void
  onDisconnect: () => void
  onResync: () => void
  onSyncLog: () => void
}

function fmt(minor: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency, minimumFractionDigits: 2 }).format(minor / 100)
  } catch {
    return `${(minor / 100).toFixed(2)}`
  }
}

export function BankDetailDrawer({ bank, plaidStatus, connectedInstitutionId, onClose, onConnect, onDisconnect, onResync, onSyncLog }: Props) {
  const { getToken } = useAuth()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(false)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)

  const isConnected = (plaidStatus === 'connected' || plaidStatus === 'syncing') &&
    (bank?.institution_id === connectedInstitutionId || connectedInstitutionId === null)

  useEffect(() => {
    setConfirmDisconnect(false)
    if (!bank || !isConnected) { setAccounts([]); setTransactions([]); return }
    setLoading(true)
    async function load() {
      try {
        const token = await getToken()
        const [ar, tr] = await Promise.all([
          fetch(`${API}/v1/integrations/plaid/accounts`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API}/v1/integrations/plaid/transactions?limit=5`, { headers: { Authorization: `Bearer ${token}` } }),
        ])
        if (ar.ok) setAccounts((await ar.json()).data ?? [])
        if (tr.ok) setTransactions((await tr.json()).data?.transactions ?? [])
      } catch { /* silent */ } finally { setLoading(false) }
    }
    load()
  }, [bank?.id, isConnected]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AnimatePresence>
      {bank && (
        <>
          <motion.div key="bank-bd" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="fixed inset-0 bg-black/70 z-40" onClick={onClose} />
          <motion.aside key="bank-dr" initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'tween', duration: 0.25 }} className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-[#111111] border-l border-[#1a2a1a] z-50 flex flex-col">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#1a2a1a]">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-sm overflow-hidden bg-white flex items-center justify-center shrink-0">
                  <Image unoptimized src={`https://www.google.com/s2/favicons?sz=64&domain=${bank.domain}`} alt={bank.name} width={24} height={24} className="object-contain" />
                </div>
                <div>
                  <h2 className="font-heading font-bold text-base text-[#e8f0e8]">{bank.name}</h2>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <StatusDot status={isConnected ? 'connected' : 'not_connected'} />
                    <StatusLabel status={isConnected ? 'connected' : 'not_connected'} />
                  </div>
                </div>
              </div>
              <button onClick={onClose} className="text-[#4a6a4a] hover:text-[#e8f0e8] transition-colors text-xl leading-none">&times;</button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              {isConnected ? (
                <>
                  {/* Accounts */}
                  <section>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a] mb-3">Bank Accounts</p>
                    {loading ? (
                      <div className="space-y-1">{[1,2].map(i => <div key={i} className="h-16 bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm animate-pulse" />)}</div>
                    ) : accounts.length > 0 ? (
                      <div className="space-y-1">
                        {accounts.map(a => (
                          <div key={a.id} className="bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm px-4 py-3 flex items-center justify-between gap-4">
                            <div className="min-w-0">
                              <p className="text-xs font-mono text-[#e8f0e8] truncate">{a.name}</p>
                              <p className="text-[10px] font-mono text-[#4a6a4a] mt-0.5 uppercase">{a.subtype || a.type}</p>
                            </div>
                            <p className="text-xs font-mono text-[#e8f0e8] shrink-0">{fmt(a.current_balance_minor, a.currency)}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[10px] font-mono text-[#4a6a4a]">No accounts yet — run a sync to load data</p>
                    )}
                  </section>

                  {/* Recent transactions */}
                  <section>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a] mb-3">Recent Transactions</p>
                    {loading ? (
                      <div className="space-y-1">{[1,2,3].map(i => <div key={i} className="h-12 bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm animate-pulse" />)}</div>
                    ) : transactions.length > 0 ? (
                      <div className="space-y-1">
                        {transactions.map(t => (
                          <div key={t.id} className="bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm px-4 py-2.5 flex items-center justify-between gap-4">
                            <div className="min-w-0">
                              <p className="text-xs font-mono text-[#e8f0e8] truncate">{t.merchant_name || t.description}</p>
                              {t.ai_category && <p className="text-[10px] font-mono text-[#4a6a4a] mt-0.5 uppercase">{t.ai_category}</p>}
                            </div>
                            <div className="text-right shrink-0">
                              <p className="text-xs font-mono text-[#e8f0e8]">{fmt(t.amount_minor, t.currency)}</p>
                              <p className="text-[10px] font-mono text-[#4a6a4a] mt-0.5">{new Date(t.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[10px] font-mono text-[#4a6a4a]">No transactions yet — run a sync to load data</p>
                    )}
                  </section>

                  {/* Actions */}
                  <section>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a] mb-3">Actions</p>
                    <div className="flex gap-2">
                      <button onClick={onResync} className="flex-1 py-2 text-[11px] font-mono text-[#e8f0e8] border border-[#1a2a1a] rounded-sm hover:bg-[#1a1a1a] transition-colors">Resync</button>
                      <button onClick={onSyncLog} className="flex-1 py-2 text-[11px] font-mono text-[#e8f0e8] border border-[#1a2a1a] rounded-sm hover:bg-[#1a1a1a] transition-colors">Sync Log</button>
                      {confirmDisconnect ? (
                        <>
                          <button onClick={() => { onDisconnect(); setConfirmDisconnect(false) }} className="flex-1 py-2 text-[11px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[#ff4d6d]/30 rounded-sm hover:bg-[rgba(255,77,109,0.15)] transition-colors">Confirm</button>
                          <button onClick={() => setConfirmDisconnect(false)} className="px-3 py-2 text-[11px] font-mono text-[#4a6a4a] border border-[#1a2a1a] rounded-sm hover:bg-[#1a1a1a] transition-colors">Cancel</button>
                        </>
                      ) : (
                        <button onClick={() => setConfirmDisconnect(true)} className="flex-1 py-2 text-[11px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.05)] border border-[#ff4d6d]/30 rounded-sm hover:bg-[rgba(255,77,109,0.1)] transition-colors">Disconnect</button>
                      )}
                    </div>
                  </section>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
                  <div className="w-16 h-16 rounded-sm overflow-hidden bg-white flex items-center justify-center">
                    <Image unoptimized src={`https://www.google.com/s2/favicons?sz=128&domain=${bank.domain}`} alt={bank.name} width={48} height={48} className="object-contain" />
                  </div>
                  <div>
                    <p className="text-sm font-mono text-[#e8f0e8]">Connect {bank.name}</p>
                    <p className="text-[10px] font-mono text-[#4a6a4a] mt-1 max-w-[240px] mx-auto">Sync accounts and transactions automatically</p>
                  </div>
                  <button onClick={() => onConnect(bank)} className="px-6 py-2.5 bg-[#00C853] text-black text-xs font-mono font-semibold rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all">
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
