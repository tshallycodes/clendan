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

export function IntegrationDetailDrawer({ slug, intg, status, lastSyncedAt, onClose, onConnect, onDisconnect, onResync, onSyncLog }: Props) {
  const { getToken } = useAuth()
  const [logs, setLogs] = useState<SyncLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
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
    if (!slug || !isConnected) return
    setLogsLoading(true)
    async function load() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/v1/integrations/${slug}/sync-log?limit=5`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          setLogs(json.data ?? [])
        }
      } catch { /* silent */ } finally { setLogsLoading(false) }
    }
    load()
  }, [slug, isConnected]) // eslint-disable-line react-hooks/exhaustive-deps

  const lastSyncDisplay = lastSyncedAt
    ? new Date(lastSyncedAt).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : '—'

  return (
    <AnimatePresence>
      {open && intg && (
        <>
          <motion.div key="intg-bd" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="fixed inset-0 bg-black/70 z-40" onClick={onClose} />
          <motion.aside key="intg-dr" initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'tween', duration: 0.25 }} className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-[#111111] border-l border-[#1a2a1a] z-50 flex flex-col">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#1a2a1a]">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-sm overflow-hidden bg-white flex items-center justify-center shrink-0">
                  <IntegrationLogo slug={intg.slug} size={32} />
                </div>
                <div>
                  <h2 className="font-heading font-bold text-base text-[#e8f0e8]">{intg.name}</h2>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <StatusDot status={status} />
                    <StatusLabel status={status} />
                  </div>
                </div>
              </div>
              <button onClick={onClose} className="text-[#4a6a4a] hover:text-[#e8f0e8] transition-colors text-xl leading-none">&times;</button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              {isConnected ? (
                <>
                  {/* Sync status */}
                  <section>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a] mb-3">Sync Status</p>
                    <div className="bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm divide-y divide-[#1a2a1a]">
                      <div className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-[10px] font-mono text-[#4a6a4a]">Last sync</span>
                        <span className="text-xs font-mono text-[#e8f0e8]">{lastSyncDisplay}</span>
                      </div>
                      <div className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-[10px] font-mono text-[#4a6a4a]">Health</span>
                        <span className="text-[10px] font-mono uppercase tracking-wider text-[#00C853]">OK</span>
                      </div>
                    </div>
                  </section>

                  {/* Recent syncs */}
                  {(logsLoading || logs.length > 0) && (
                    <section>
                      <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a] mb-3">Recent Syncs</p>
                      {logsLoading ? (
                        <div className="space-y-1">{[1, 2, 3].map((i) => <div key={i} className="h-10 bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm animate-pulse" />)}</div>
                      ) : (
                        <div className="space-y-1">
                          {logs.map((entry) => (
                            <div key={entry.id} className="bg-[#0a0a0a] border border-[#1a2a1a] rounded-sm px-4 py-2.5 flex items-center justify-between gap-4">
                              <span className="text-xs font-mono text-[#e8f0e8] truncate">{entry.entity_type}</span>
                              <div className="flex items-center gap-3 shrink-0">
                                <span className={`text-[10px] font-mono uppercase ${statusColor(entry.status)}`}>{entry.status}</span>
                                <span className="text-[10px] font-mono text-[#4a6a4a]">{new Date(entry.timestamp).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {/* Actions */}
                  <section>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a] mb-3">Actions</p>
                    <div className="flex gap-2">
                      <button
                        disabled={resyncing}
                        onClick={async () => {
                          setResyncing(true)
                          try { await onResync() } finally { setResyncing(false) }
                        }}
                        className="flex-1 py-2 text-[11px] font-mono text-[#e8f0e8] border border-[#1a2a1a] rounded-sm hover:bg-[#1a1a1a] transition-colors disabled:opacity-60"
                      >
                        {resyncing ? 'Syncing...' : 'Resync'}
                      </button>
                      <button onClick={onSyncLog} className="flex-1 py-2 text-[11px] font-mono text-[#e8f0e8] border border-[#1a2a1a] rounded-sm hover:bg-[#1a1a1a] transition-colors">Sync Log</button>
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
                    <IntegrationLogo slug={intg.slug} size={48} />
                  </div>
                  <div>
                    <p className="text-sm font-mono text-[#e8f0e8]">{intg.name}</p>
                    <p className="text-[10px] font-mono text-[#4a6a4a] mt-1 max-w-[240px] mx-auto">{intg.desc}</p>
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
