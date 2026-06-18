'use client'

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { IntegrationLogo } from './IntegrationLogo'
import { StatusDot, StatusLabel } from './CardStatusIndicator'
import { IntegrationDef, IntegrationStatus } from './types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface SyncLogEntry {
  id: string
  entity_type: string
  status: string
  timestamp: string
}

interface AccountSummary {
  // FreshBooks-style rich accounting summary
  total_invoices?: number
  outstanding_invoices?: number
  outstanding_amount_cents?: number
  overdue_invoices?: number
  overdue_amount_cents?: number
  total_clients?: number
  total_payments?: number
  total_payments_amount_cents?: number
  total_expenses?: number
  total_expenses_amount_cents?: number
  // Xero / QuickBooks-style entity counts
  invoices?: number
  bills?: number
  contacts?: number
  payments?: number
  expenses?: number
  accounts?: number
  credit_notes?: number
  tax_rates?: number
  [key: string]: number | string | undefined
}

interface Props {
  slug: string | null
  intg: IntegrationDef | null
  status: IntegrationStatus
  lastSyncedAt: string | null
  onClose: () => void
  onConnect: () => void
  onDisconnect: () => Promise<void>
  onResync: () => Promise<void>
  onSyncLog: () => void
}

function statusColor(s: string): string {
  if (s === 'success' || s === 'completed') return 'text-[#00C853]'
  if (s === 'error' || s === 'failed') return 'text-[#ff4d6d]'
  return 'text-[#00a8cc]'
}

function formatCents(cents: number): string {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 }).format(cents / 100)
}

const ALL_SUMMARY_SLUGS = new Set([
  'freshbooks', 'xero', 'quickbooks',
  'stripe', 'square', 'gocardless', 'adyen', 'wise',
  'hubspot', 'salesforce',
  'gmail', 'outlook', 'google-drive', 'dropbox', 'onedrive',
  'netsuite', 'sap', 'dynamics365',
  'sage',
])

export function IntegrationDetailDrawer({ slug, intg, status, lastSyncedAt, onClose, onConnect, onDisconnect, onResync, onSyncLog }: Props) {
  const { getToken } = useAuth()
  const [logs, setLogs] = useState<SyncLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [summary, setSummary] = useState<AccountSummary | null>(null)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [resyncing, setResyncing] = useState(false)

  const open = slug !== null && intg !== null
  const isConnected = status === 'connected' || status === 'syncing'

  useEffect(() => {
    setConfirmDisconnect(false)
    setDisconnecting(false)
    setResyncing(false)
    setLogs([])
    setSummary(null)
    if (!slug || !isConnected) return

    setLogsLoading(true)

    async function load() {
      try {
        const token = await getToken()

        const logsRes = await fetch(`${API}/v1/integrations/${slug}/sync-log?limit=5`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (logsRes.ok) {
          const json = await logsRes.json()
          setLogs(json.data ?? [])
        }

        if (slug && ALL_SUMMARY_SLUGS.has(slug)) {
          const sumRes = await fetch(`${API}/v1/integrations/${slug}/status`, {
            headers: { Authorization: `Bearer ${token}` },
          })
          if (sumRes.ok) {
            const json = await sumRes.json()
            setSummary(json.data?.summary ?? null)
          }
        }
      } catch { /* silent */ } finally { setLogsLoading(false) }
    }

    load()
  }, [slug, status]) // eslint-disable-line react-hooks/exhaustive-deps

  const lastSyncDisplay = lastSyncedAt
    ? new Date(lastSyncedAt).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : '—'

  return (
    <AnimatePresence>
      {open && intg && (
        <>
          <motion.div key="intg-bd" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="fixed inset-0 z-40" onClick={onClose} />
          <motion.aside key="intg-dr" initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'tween', duration: 0.25 }} className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-brand-surface border-l border-brand-border z-50 flex flex-col">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-sm overflow-hidden bg-white flex items-center justify-center shrink-0">
                  <IntegrationLogo slug={intg.slug} size={32} />
                </div>
                <div>
                  <h2 className="font-heading font-bold text-base text-brand-text">{intg.name}</h2>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <StatusDot status={status} />
                    <StatusLabel status={status} />
                  </div>
                </div>
              </div>
              <button onClick={onClose} className="text-brand-muted hover:text-brand-text transition-colors text-xl leading-none">&times;</button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              {isConnected ? (
                <>
                  {/* Account summary */}
                  {summary && (
                    <section>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted mb-3">Account Summary</p>
                      <div className="grid grid-cols-2 gap-2">
                        {/* FreshBooks-style: rich accounting summary with amounts */}
                        {summary.total_invoices !== undefined && (
                          <SummaryCard label="Invoices" value={String(summary.total_invoices)} />
                        )}
                        {summary.outstanding_invoices !== undefined && summary.outstanding_amount_cents !== undefined && (
                          <SummaryCard
                            label="Outstanding"
                            value={String(summary.outstanding_invoices)}
                            sub={formatCents(summary.outstanding_amount_cents)}
                            accent={(summary.outstanding_invoices as number) > 0 ? 'warn' : 'ok'}
                          />
                        )}
                        {summary.overdue_invoices !== undefined && summary.overdue_amount_cents !== undefined && (
                          <SummaryCard
                            label="Overdue"
                            value={String(summary.overdue_invoices)}
                            sub={(summary.overdue_invoices as number) > 0 ? formatCents(summary.overdue_amount_cents as number) : undefined}
                            accent={(summary.overdue_invoices as number) > 0 ? 'danger' : 'ok'}
                          />
                        )}
                        {summary.total_clients !== undefined && (
                          <SummaryCard label="Clients" value={String(summary.total_clients)} />
                        )}
                        {summary.total_payments !== undefined && summary.total_payments_amount_cents !== undefined && (
                          <SummaryCard
                            label="Payments"
                            value={String(summary.total_payments)}
                            sub={formatCents(summary.total_payments_amount_cents as number)}
                            accent="ok"
                          />
                        )}
                        {summary.total_expenses !== undefined && summary.total_expenses_amount_cents !== undefined && (
                          <SummaryCard
                            label="Expenses"
                            value={String(summary.total_expenses)}
                            sub={formatCents(summary.total_expenses_amount_cents as number)}
                          />
                        )}
                        {/* Xero / QuickBooks-style: entity counts only */}
                        {summary.total_invoices === undefined && summary.invoices !== undefined && (
                          <SummaryCard label="Invoices" value={String(summary.invoices)} />
                        )}
                        {summary.total_invoices === undefined && summary.bills !== undefined && (
                          <SummaryCard label="Bills" value={String(summary.bills)} />
                        )}
                        {summary.total_invoices === undefined && summary.contacts !== undefined && (
                          <SummaryCard label="Contacts" value={String(summary.contacts)} />
                        )}
                        {summary.total_invoices === undefined && summary.payments !== undefined && (
                          <SummaryCard label="Payments" value={String(summary.payments)} accent="ok" />
                        )}
                        {summary.total_invoices === undefined && summary.expenses !== undefined && (
                          <SummaryCard label="Expenses" value={String(summary.expenses)} />
                        )}
                        {summary.total_invoices === undefined && summary.accounts !== undefined && (
                          <SummaryCard label="Accounts" value={String(summary.accounts)} />
                        )}
                        {summary.total_invoices === undefined && summary.credit_notes !== undefined && (
                          <SummaryCard label="Credit Notes" value={String(summary.credit_notes)} />
                        )}
                        {summary.total_invoices === undefined && summary.tax_rates !== undefined && (
                          <SummaryCard label="Tax Rates" value={String(summary.tax_rates)} />
                        )}
                      </div>
                    </section>
                  )}

                  {/* Sync status */}
                  <section>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted mb-3">Sync Status</p>
                    <div className="bg-brand-bg border border-brand-border rounded-sm divide-y divide-brand-border">
                      <div className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-[10px] font-mono text-brand-muted">Last sync</span>
                        <span className="text-xs font-mono text-brand-text">{lastSyncDisplay}</span>
                      </div>
                      <div className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-[10px] font-mono text-brand-muted">Health</span>
                        <span className="text-[10px] font-mono uppercase tracking-wider text-[#00C853]">OK</span>
                      </div>
                    </div>
                  </section>

                  {/* Recent syncs */}
                  {(logsLoading || logs.length > 0) && (
                    <section>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted mb-3">Recent Syncs</p>
                      {logsLoading ? (
                        <div className="space-y-1">{[1, 2, 3].map((i) => <div key={i} className="h-10 bg-brand-bg border border-brand-border rounded-sm animate-pulse" />)}</div>
                      ) : (
                        <div className="space-y-1">
                          {logs.map((entry) => (
                            <div key={entry.id} className="bg-brand-bg border border-brand-border rounded-sm px-4 py-2.5 flex items-center justify-between gap-4">
                              <span className="text-xs font-mono text-brand-text truncate">{entry.entity_type}</span>
                              <div className="flex items-center gap-3 shrink-0">
                                <span className={`text-[10px] font-mono uppercase ${statusColor(entry.status)}`}>{entry.status}</span>
                                <span className="text-[10px] font-mono text-brand-muted">{new Date(entry.timestamp).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {/* Actions */}
                  <section>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted mb-3">Actions</p>
                    <div className="flex gap-2">
                      <button
                        disabled={resyncing}
                        onClick={async () => {
                          setResyncing(true)
                          try { await onResync() } finally { setResyncing(false) }
                        }}
                        className="flex-1 py-2 text-[11px] font-mono text-brand-text border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors disabled:opacity-60"
                      >
                        {resyncing ? 'Syncing...' : 'Resync'}
                      </button>
                      <button onClick={onSyncLog} className="flex-1 py-2 text-[11px] font-mono text-brand-text border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors">Sync Log</button>
                      {confirmDisconnect ? (
                        <>
                          <button
                            disabled={disconnecting}
                            onClick={async () => {
                              setDisconnecting(true)
                              try { await onDisconnect() } finally { setDisconnecting(false); setConfirmDisconnect(false) }
                            }}
                            className="flex-1 py-2 text-[11px] font-mono text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[#ff4d6d]/30 rounded-sm hover:bg-[rgba(255,77,109,0.15)] transition-colors disabled:opacity-60"
                          >
                            {disconnecting ? 'Disconnecting...' : 'Confirm'}
                          </button>
                          <button onClick={() => setConfirmDisconnect(false)} className="px-3 py-2 text-[11px] font-mono text-brand-muted border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors">Cancel</button>
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
                    <IntegrationLogo slug={intg.slug} size={48} />
                  </div>
                  <div>
                    <p className="text-sm font-mono text-brand-text">{intg.name}</p>
                    <p className="text-[10px] font-mono text-brand-muted mt-1 max-w-[240px] mx-auto">{intg.desc}</p>
                  </div>
                  <button onClick={onConnect} className="px-6 py-2.5 bg-[#00C853] text-black text-xs font-mono font-semibold rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all">
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

interface SummaryCardProps {
  label: string
  value: string
  sub?: string
  accent?: 'ok' | 'warn' | 'danger'
}

function SummaryCard({ label, value, sub, accent }: SummaryCardProps) {
  const valueColor =
    accent === 'ok' ? 'text-[#00C853]' :
    accent === 'danger' ? 'text-[#ff4d6d]' :
    accent === 'warn' ? 'text-[#f5a623]' :
    'text-brand-text'

  return (
    <div className="bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
      <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted mb-1">{label}</p>
      <p className={`text-xl font-mono font-semibold ${valueColor}`}>{value}</p>
      {sub && <p className="text-[10px] font-mono text-brand-muted mt-0.5">{sub}</p>}
    </div>
  )
}

