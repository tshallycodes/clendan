'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { IntegrationDef, IntegrationStatus } from './types'
import { StatusDot, StatusLabel, leftBorderClass } from './CardStatusIndicator'
import { IntegrationLogo } from './IntegrationLogo'

interface IntegrationCardProps {
  intg: IntegrationDef
  status: IntegrationStatus
  onConnect: () => void
  onDisconnect: () => void
  onResync: () => void
  onViewLog: () => void
  lastSyncedAt: string | null
  confirming: boolean
  onCancelConfirm: () => void
  connecting: boolean
  disconnecting: boolean
}

export function IntegrationCard({
  intg,
  status,
  onConnect,
  onDisconnect,
  onResync,
  onViewLog,
  lastSyncedAt,
  confirming,
  onCancelConfirm,
  connecting,
  disconnecting,
}: IntegrationCardProps) {
  const isActive = status !== 'not_connected' && status !== 'disconnected'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={[
        'bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3 transition-colors',
        leftBorderClass(status),
      ].join(' ')}
    >
      <div className="flex items-start gap-3">
        <IntegrationLogo slug={intg.slug} size={20} />
        <div className="space-y-0.5 min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-mono text-brand-text font-medium truncate">{intg.name}</span>
            {isActive && (
              <div className="flex items-center gap-1.5 shrink-0">
                <StatusDot status={status} />
                <StatusLabel status={status} />
              </div>
            )}
          </div>
          <p className="text-xs font-mono text-brand-muted">{intg.desc}</p>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {status === 'connected' && (
          <motion.div key="connected-actions" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="space-y-2">
            <p className="text-[10px] font-mono text-brand-muted">
              Last sync: {lastSyncedAt ? new Date(lastSyncedAt).toLocaleString() : '—'}
            </p>
            {disconnecting ? (
              <p className="text-[10px] font-mono text-[#4a6a4a]">Disconnecting...</p>
            ) : confirming ? (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] font-mono text-[#ff4d6d]">Disconnect {intg.name}?</span>
                <button type="button" onClick={onDisconnect} className="text-[10px] font-mono bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] rounded-sm px-2 py-0.5 hover:bg-[rgba(255,77,109,0.2)] transition-colors">
                  Confirm
                </button>
                <button type="button" onClick={onCancelConfirm} className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors">
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <button type="button" onClick={onResync} className="text-[10px] font-mono border border-brand-border text-brand-secondary rounded-sm px-2 py-0.5 hover:border-brand-border-subtle hover:text-brand-text transition-colors">
                  Resync
                </button>
                <button type="button" onClick={onViewLog} className="text-[10px] font-mono border border-brand-border text-brand-secondary rounded-sm px-2 py-0.5 hover:border-brand-border-subtle hover:text-brand-text transition-colors">
                  Sync log
                </button>
                <button type="button" onClick={onDisconnect} className="text-[10px] font-mono bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] rounded-sm px-2 py-0.5 hover:bg-[rgba(255,77,109,0.2)] transition-colors">
                  Disconnect
                </button>
              </div>
            )}
          </motion.div>
        )}

        {status === 'error' && (
          <motion.div key="error-actions" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <p className="text-[10px] font-mono text-[#ff4d6d] mb-2">Connection error — check credentials</p>
            <button type="button" onClick={onConnect} disabled={connecting} className="text-xs font-mono bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 transition-all disabled:opacity-50">
              {connecting ? 'Reconnecting...' : 'Reconnect'}
            </button>
          </motion.div>
        )}

        {(status === 'connecting' || status === 'syncing') && (
          <motion.div key="loading-state" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <p className="text-[10px] font-mono text-[#00a8cc]">
              {status === 'connecting' ? 'Connecting...' : 'Syncing data...'}
            </p>
          </motion.div>
        )}

        {(status === 'not_connected' || status === 'disconnected') && (
          <motion.div key="connect-action" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <button type="button" onClick={onConnect} disabled={connecting} className="text-xs font-mono bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 transition-all disabled:opacity-50">
              {connecting ? 'Connecting...' : 'Connect'}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
