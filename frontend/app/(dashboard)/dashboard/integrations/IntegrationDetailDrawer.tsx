'use client'

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { IntegrationLogo } from './IntegrationLogo'
import { StatusDot, StatusLabel } from './CardStatusIndicator'
import { IntegrationDef, IntegrationStatus } from './types'
import { useCurrency } from '@/components/Providers'

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
  // Payment provider counts
  charges?: number
  mandates?: number
  payouts?: number
  // Document storage counts
  files?: number
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

// What Clendan can operate in each connection, grounded in the operator model + real API
// coverage. level: yes = supported · limited = partial/API-gated · no = out of scope.
type Cap = { label: string; level: 'yes' | 'limited' | 'no' }

function capabilitiesFor(slug: string, category: string): Cap[] {
  if (category === 'Accounting') {
    const noGl = slug === 'freshbooks' // FreshBooks has no journal / reports API
    return [
      { label: 'Read reports (P&L, balance sheet, VAT)', level: noGl ? 'no' : 'yes' },
      { label: 'Create & post bills', level: 'yes' },
      { label: 'Post journal entries', level: noGl ? 'no' : 'yes' },
      { label: 'Reconcile bank ↔ ledger', level: 'limited' },
      { label: 'Prepare payments — never disburses', level: 'yes' },
    ]
  }
  if (category === 'Payments') {
    return [
      { label: 'Read revenue & charges', level: 'yes' },
      { label: 'Move money', level: 'no' },
    ]
  }
  if (category === 'ERP') {
    return [
      { label: 'Sync ledger data', level: 'yes' },
      { label: 'Post bills & journals', level: 'limited' },
    ]
  }
  if (category === 'Document & Email') {
    const email = slug === 'gmail' || slug === 'outlook'
    return [
      { label: 'Ingest invoices & receipts', level: 'yes' },
      { label: 'Send collection reminders', level: email ? 'yes' : 'no' },
    ]
  }
  return [{ label: 'Read data', level: 'yes' }]
}

function statusColor(s: string): string {
  if (s === 'success' || s === 'completed') return 'text-[#00C853]'
  if (s === 'error' || s === 'failed') return 'text-[#ff4d6d]'
  return 'text-[#00a8cc]'
}

const ALL_SUMMARY_SLUGS = new Set([
  'freshbooks', 'xero', 'quickbooks',
  'stripe', 'square', 'gocardless', 'adyen', 'wise',
  'gmail', 'outlook', 'google-drive', 'dropbox', 'onedrive',
  'netsuite', 'sap', 'dynamics365',
  'sage',
])

// Sources that scope ingestion so only matching documents are processed. A file/email
// outside the scope is never read.
const WATCH_FOLDER_SLUGS = new Set(['google-drive', 'dropbox', 'gmail', 'outlook'])
const EMAIL_SLUGS = new Set(['gmail', 'outlook'])
const FOLDER_PLACEHOLDER: Record<string, string> = {
  'google-drive': 'e.g. Invoices',
  'dropbox': 'e.g. /Clendan',
  'gmail': 'e.g. (invoice OR bill)  ·  from:supplier.com  ·  label:Invoices',
  'outlook': "e.g. contains(subject,'invoice')",
}

// The recommended keyword filter, prefilled for a freshly-connected email source so the
// broad "catch invoices from any supplier" default is one click (Save) away. Gmail already
// scopes to has:attachment, so this is just the keyword part (parenthesised for correct OR).
const RECOMMENDED_EMAIL_FILTER: Record<string, string> = {
  'gmail': '(invoice OR bill)',
  'outlook': "(contains(subject,'invoice') or contains(subject,'bill'))",
}

export function IntegrationDetailDrawer({ slug, intg, status, lastSyncedAt, onClose, onConnect, onDisconnect, onResync, onSyncLog }: Props) {
  const { getToken } = useAuth()
  const { convert } = useCurrency()
  const [logs, setLogs] = useState<SyncLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [summary, setSummary] = useState<AccountSummary | null>(null)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [resyncing, setResyncing] = useState(false)
  const [watchFolder, setWatchFolder] = useState('')
  const [folderInput, setFolderInput] = useState('')
  const [savingFolder, setSavingFolder] = useState(false)
  const [folderSaved, setFolderSaved] = useState(false)

  const open = slug !== null && intg !== null
  const isConnected = status === 'connected' || status === 'syncing'
  const isWatchFolderSource = slug !== null && WATCH_FOLDER_SLUGS.has(slug)
  const isEmailSource = slug !== null && EMAIL_SLUGS.has(slug)

  useEffect(() => {
    setConfirmDisconnect(false)
    setDisconnecting(false)
    setResyncing(false)
    setLogs([])
    setSummary(null)
    setWatchFolder('')
    setFolderInput('')
    setFolderSaved(false)
    if (!slug || !isConnected) return

    setLogsLoading(true)

    async function load() {
      try {
        const token = await getToken()

        const logsRes = await fetch(`${API}/integrations/${slug}/sync-log?limit=5`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (logsRes.ok) {
          const json = await logsRes.json()
          setLogs(json.data ?? [])
        }

        if (slug && ALL_SUMMARY_SLUGS.has(slug)) {
          const sumRes = await fetch(`${API}/integrations/${slug}/status`, {
            headers: { Authorization: `Bearer ${token}` },
          })
          if (sumRes.ok) {
            const json = await sumRes.json()
            setSummary(json.data?.summary ?? null)
            const wf = json.data?.watch_folder ?? ''
            setWatchFolder(wf)
            // Nudge new email sources toward the recommended keyword filter: prefill it
            // (unsaved) so it is one Save click away, without silently reading the mailbox.
            const isEmail = slug !== null && EMAIL_SLUGS.has(slug)
            setFolderInput(wf || (isEmail ? (RECOMMENDED_EMAIL_FILTER[slug ?? ''] ?? '') : ''))
          }
        }
      } catch { /* silent */ } finally { setLogsLoading(false) }
    }

    load()
  }, [slug, status]) // eslint-disable-line react-hooks/exhaustive-deps

  async function saveWatchFolder() {
    if (!slug) return
    setSavingFolder(true)
    setFolderSaved(false)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/integrations/${slug}/watch-folder`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: folderInput.trim() }),
      })
      if (res.ok) {
        const json = await res.json()
        setWatchFolder(json.data?.watch_folder ?? '')
        setFolderSaved(true)
        setTimeout(() => setFolderSaved(false), 6000)
      }
    } catch { /* silent */ } finally {
      setSavingFolder(false)
    }
  }

  const lastSyncDisplay = lastSyncedAt
    ? new Date(lastSyncedAt).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : '-'

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
              {/* What Clendan can operate here */}
              <section>
                <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-3">What Clendan can do here</p>
                <div className="space-y-1.5">
                  {capabilitiesFor(intg.slug, intg.category).map((c) => (
                    <div key={c.label} className="flex items-center gap-2 text-xs font-body">
                      <span className={c.level === 'yes' ? 'text-[#00C853]' : c.level === 'limited' ? 'text-[#f5a623]' : 'text-brand-muted'}>
                        {c.level === 'yes' ? '✓' : c.level === 'limited' ? '≈' : '✕'}
                      </span>
                      <span className={c.level === 'no' ? 'text-brand-muted' : 'text-brand-secondary'}>{c.label}</span>
                      {c.level === 'limited' && <span className="text-[10px] font-body text-brand-muted">(API-limited)</span>}
                    </div>
                  ))}
                </div>
              </section>

              {isConnected ? (
                <>
                  {/* Account summary */}
                  {summary && (
                    <section>
                      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-3">Account Summary</p>
                      <div className="grid grid-cols-2 gap-2">
                        {/* FreshBooks-style: rich accounting summary with amounts */}
                        {summary.total_invoices !== undefined && (
                          <SummaryCard label="Invoices" value={String(summary.total_invoices)} />
                        )}
                        {summary.outstanding_invoices !== undefined && summary.outstanding_amount_cents !== undefined && (
                          <SummaryCard
                            label="Outstanding"
                            value={String(summary.outstanding_invoices)}
                            sub={convert(summary.outstanding_amount_cents, 'GBP')}
                            accent={(summary.outstanding_invoices as number) > 0 ? 'warn' : 'ok'}
                          />
                        )}
                        {summary.overdue_invoices !== undefined && summary.overdue_amount_cents !== undefined && (
                          <SummaryCard
                            label="Overdue"
                            value={String(summary.overdue_invoices)}
                            sub={(summary.overdue_invoices as number) > 0 ? convert(summary.overdue_amount_cents as number, 'GBP') : undefined}
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
                            sub={convert(summary.total_payments_amount_cents as number, 'GBP')}
                            accent="ok"
                          />
                        )}
                        {summary.total_expenses !== undefined && summary.total_expenses_amount_cents !== undefined && (
                          <SummaryCard
                            label="Expenses"
                            value={String(summary.total_expenses)}
                            sub={convert(summary.total_expenses_amount_cents as number, 'GBP')}
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
                        {summary.total_invoices === undefined && summary.charges !== undefined && (
                          <SummaryCard label="Charges" value={String(summary.charges)} accent="ok" />
                        )}
                        {summary.total_invoices === undefined && summary.mandates !== undefined && (
                          <SummaryCard label="Mandates" value={String(summary.mandates)} />
                        )}
                        {summary.total_invoices === undefined && summary.payouts !== undefined && (
                          <SummaryCard label="Payouts" value={String(summary.payouts)} accent="ok" />
                        )}
                        {summary.files !== undefined && (
                          <SummaryCard label="PDF Files" value={String(summary.files)} />
                        )}
                      </div>
                    </section>
                  )}

                  {/* Ingestion scope (document + email sources) */}
                  {isWatchFolderSource && (
                    <section>
                      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-1">Document Processing</p>
                      <p className="text-[11px] font-body text-brand-muted mb-3 leading-relaxed">
                        {isEmailSource
                          ? 'Only emails matching this filter are read; the rest of your mailbox is ignored. You can cast a wide net (e.g. invoice OR bill) - Clen classifies every attachment and only acts on invoices and receipts, ignoring the rest. Leave empty to process nothing.'
                          : 'Only files inside this folder are read and processed. Everything else in your account is ignored. Leave empty to process nothing.'}
                      </p>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={folderInput}
                          onChange={(e) => { setFolderInput(e.target.value); setFolderSaved(false) }}
                          placeholder={FOLDER_PLACEHOLDER[slug ?? ''] ?? 'Folder name'}
                          className="flex-1 bg-brand-bg border border-brand-border focus:border-[#00C853] rounded-sm px-3 py-2 text-xs font-body text-brand-text placeholder:text-brand-muted outline-none transition-colors"
                        />
                        <button
                          onClick={saveWatchFolder}
                          disabled={savingFolder || folderInput.trim() === watchFolder}
                          className="px-4 py-2 text-[12px] font-body text-brand-text border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors disabled:opacity-50"
                        >
                          {savingFolder ? 'Saving…' : 'Save'}
                        </button>
                      </div>
                      {isEmailSource && !watchFolder && !folderSaved
                        && folderInput.trim() === (RECOMMENDED_EMAIL_FILTER[slug ?? ''] ?? '') && (
                        <p className="text-[11px] font-body text-brand-muted mt-2">
                          Recommended filter shown - catches invoices from any supplier. Click Save to apply, or edit it.
                        </p>
                      )}
                      {folderSaved && (
                        <p className="text-[11px] font-body text-[#00C853] mt-2">
                          {watchFolder
                            ? (isEmailSource
                                ? 'Saved. Matching emails will appear in Documents as they are processed.'
                                : `Saved. Files in ${watchFolder} will appear in Documents as they are processed.`)
                            : 'Saved. Processing paused (nothing set).'}
                        </p>
                      )}
                    </section>
                  )}

                  {/* Sync status */}
                  <section>
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-3">Sync Status</p>
                    <div className="bg-brand-bg border border-brand-border rounded-sm divide-y divide-brand-border">
                      <div className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-[11px] font-body text-brand-muted">Last sync</span>
                        <span className="text-xs font-body text-brand-text">{lastSyncDisplay}</span>
                      </div>
                      <div className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-[11px] font-body text-brand-muted">Health</span>
                        <span className="text-[11px] font-body uppercase tracking-wider text-[#00C853]">OK</span>
                      </div>
                    </div>
                  </section>

                  {/* Recent syncs */}
                  {(logsLoading || logs.length > 0) && (
                    <section>
                      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-3">Recent Syncs</p>
                      {logsLoading ? (
                        <div className="space-y-1">{[1, 2, 3].map((i) => <div key={i} className="h-10 bg-brand-bg border border-brand-border rounded-sm animate-pulse" />)}</div>
                      ) : (
                        <div className="space-y-1">
                          {logs.map((entry) => (
                            <div key={entry.id} className="bg-brand-bg border border-brand-border rounded-sm px-4 py-2.5 flex items-center justify-between gap-4">
                              <span className="text-xs font-body text-brand-text truncate">{entry.entity_type}</span>
                              <div className="flex items-center gap-3 shrink-0">
                                <span className={`text-[11px] font-body uppercase ${statusColor(entry.status)}`}>{entry.status}</span>
                                <span className="text-[11px] font-body text-brand-muted">{new Date(entry.timestamp).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {/* Actions */}
                  <section>
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-3">Actions</p>
                    <div className="flex gap-2">
                      <button
                        disabled={resyncing}
                        onClick={async () => {
                          setResyncing(true)
                          try { await onResync() } finally { setResyncing(false) }
                        }}
                        className="flex-1 py-2 text-[12px] font-body text-brand-text border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors disabled:opacity-60"
                      >
                        {resyncing ? 'Syncing...' : 'Resync'}
                      </button>
                      <button onClick={onSyncLog} className="flex-1 py-2 text-[12px] font-body text-brand-text border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors">Sync Log</button>
                      {confirmDisconnect ? (
                        <>
                          <button
                            disabled={disconnecting}
                            onClick={async () => {
                              setDisconnecting(true)
                              try { await onDisconnect() } finally { setDisconnecting(false); setConfirmDisconnect(false) }
                            }}
                            className="flex-1 py-2 text-[12px] font-body text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[#ff4d6d]/30 rounded-sm hover:bg-[rgba(255,77,109,0.15)] transition-colors disabled:opacity-60"
                          >
                            {disconnecting ? 'Disconnecting...' : 'Confirm'}
                          </button>
                          <button onClick={() => setConfirmDisconnect(false)} className="px-3 py-2 text-[12px] font-body text-brand-muted border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors">Cancel</button>
                        </>
                      ) : (
                        <button onClick={() => setConfirmDisconnect(true)} className="flex-1 py-2 text-[12px] font-body text-[#ff4d6d] bg-[rgba(255,77,109,0.05)] border border-[#ff4d6d]/30 rounded-sm hover:bg-[rgba(255,77,109,0.1)] transition-colors">Disconnect</button>
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
                    <p className="text-sm font-body text-brand-text">{intg.name}</p>
                    <p className="text-[11px] font-body text-brand-muted mt-1 max-w-[240px] mx-auto">{intg.desc}</p>
                  </div>
                  <button onClick={onConnect} className="px-6 py-2.5 bg-[#00C853] text-black text-xs font-body font-semibold rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all">
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
      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted mb-1">{label}</p>
      <p className={`text-xl font-body font-semibold ${valueColor}`}>{value}</p>
      {sub && <p className="text-[11px] font-body text-brand-muted mt-0.5">{sub}</p>}
    </div>
  )
}

