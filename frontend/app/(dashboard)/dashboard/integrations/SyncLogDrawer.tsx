'use client'

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { SyncEvent } from './types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface SyncLogDrawerProps {
  slug: string | null
  integrationName: string
  onClose: () => void
}

function statusColor(status: string): string {
  if (status === 'success' || status === 'completed') return 'text-[#00C853]'
  if (status === 'error' || status === 'failed') return 'text-[#ff4d6d]'
  return 'text-[#00a8cc]'
}

export function SyncLogDrawer({ slug, integrationName, onClose }: SyncLogDrawerProps) {
  const { getToken } = useAuth()
  const [events, setEvents] = useState<SyncEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [supportsLog, setSupportsLog] = useState(true)

  useEffect(() => {
    if (!slug) return
    setEvents([])
    setSupportsLog(true)
    setLoading(true)

    async function fetchLog() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/v1/integrations/${slug}/sync-log`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.status === 404 || res.status === 501) {
          setSupportsLog(false)
          return
        }
        if (!res.ok) {
          setSupportsLog(false)
          return
        }
        const json = await res.json()
        const data: SyncEvent[] = json.data ?? json ?? []
        setEvents(data)
      } catch {
        setSupportsLog(false)
      } finally {
        setLoading(false)
      }
    }

    fetchLog()
  }, [slug, getToken])

  const open = slug !== null

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="log-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40"
            onClick={onClose}
          />
          <motion.aside
            key="log-drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.25 }}
            className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-[#111111] border-l border-brand-border z-50 flex flex-col"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
              <div>
                <h2 className="font-heading font-bold text-base text-[#e8f0e8]">Sync Log</h2>
                <p className="text-[10px] font-mono text-brand-muted mt-0.5 uppercase tracking-widest">
                  {integrationName}
                </p>
              </div>
              <button
                onClick={onClose}
                className="text-brand-muted hover:text-[#e8f0e8] transition-colors text-xl leading-none"
                aria-label="Close"
              >
                &times;
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4">
              {loading && (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-12 bg-[#1a1a1a] rounded-sm animate-pulse" />
                  ))}
                </div>
              )}

              {!loading && (!supportsLog || events.length === 0) && (
                <div className="flex flex-col items-center justify-center h-40 gap-1">
                  <p className="text-xs font-mono text-brand-secondary">No sync events yet</p>
                  <p className="text-[10px] font-mono text-brand-muted">Events will appear here after the first sync</p>
                </div>
              )}

              {!loading && supportsLog && events.length > 0 && (
                <div className="space-y-1">
                  {events.map((event, idx) => (
                    <motion.div
                      key={event.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05, duration: 0.15 }}
                      className="bg-[#0a0a0a] border border-brand-border rounded-sm px-4 py-3"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-[#e8f0e8] truncate">{event.entity_type}</span>
                            <span className={`text-[10px] font-mono uppercase tracking-wider ${statusColor(event.status)}`}>
                              {event.status}
                            </span>
                          </div>
                          {event.records_synced > 0 && (
                            <p className="text-[10px] font-mono text-brand-muted mt-0.5">
                              {event.records_synced} records
                            </p>
                          )}
                        </div>
                        <time className="text-[10px] font-mono text-brand-muted shrink-0">
                          {new Date(event.timestamp).toLocaleString()}
                        </time>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

