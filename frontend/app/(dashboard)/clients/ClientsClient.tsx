'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { useRouter } from 'next/navigation'
import { Buildings } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/Providers'
import {
  getActiveClient,
  setActiveClient,
  type FirmClient,
} from '@/components/dashboard/ClientSwitcher'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const pageVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}
const cardListVariants = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } }
const cardVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-lg font-heading font-bold text-brand-text tabular-nums">{value}</div>
      <div className="text-[10px] font-body uppercase tracking-widest text-brand-muted mt-0.5">{label}</div>
    </div>
  )
}

export function ClientsClient({ initialClients }: { initialClients: FirmClient[] }) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const router = useRouter()
  const [clients] = useState<FirmClient[]>(initialClients)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  useEffect(() => {
    setActiveId(getActiveClient())
  }, [])

  async function openClient(client: FirmClient) {
    setLoadingId(client.tenant_id)
    try {
      const token = await getToken()
      if (token) {
        const res = await fetch(`${API_BASE}/firms/clients/${client.tenant_id}/act-as`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        })
        if (!res.ok) {
          toast('Could not switch client — check your firm access', 'error')
          return
        }
      }
      setActiveClient(client.tenant_id)
      setActiveId(client.tenant_id)
      toast(`Now acting as ${client.name}`, 'success')
      router.refresh()
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-6">
      <motion.div variants={sectionVariants}>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Clients</h1>
        <p className="text-brand-muted text-xs font-body mt-1">
          {clients.length > 0
            ? `${clients.length} client ${clients.length === 1 ? 'workspace' : 'workspaces'} in your firm portfolio`
            : 'Your firm portfolio'}
        </p>
      </motion.div>

      {clients.length === 0 ? (
        <motion.div
          variants={sectionVariants}
          className="bg-brand-surface border border-brand-border rounded-sm p-12 flex flex-col items-center gap-3 text-center"
        >
          <Buildings className="w-6 h-6 text-brand-muted" />
          <p className="text-xs font-body text-brand-muted max-w-sm">
            No client workspaces yet. This appears when your account belongs to an accounting
            firm operating a portfolio of client tenants.
          </p>
        </motion.div>
      ) : (
        <motion.div variants={cardListVariants} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {clients.map((client) => {
            const isActive = activeId === client.tenant_id
            return (
              <motion.div
                key={client.tenant_id}
                variants={cardVariants}
                className={cn(
                  'bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-4',
                  isActive && 'border-l-[3px] border-l-brand-green',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-heading font-semibold text-brand-text truncate">
                      {client.name}
                    </div>
                    {isActive && (
                      <span className="inline-block mt-1 text-[10px] font-body uppercase tracking-widest text-brand-green">
                        Active
                      </span>
                    )}
                  </div>
                  <Buildings className="w-4 h-4 text-brand-muted shrink-0" />
                </div>

                <div className="flex items-center gap-8">
                  <Metric value={client.pending_approvals} label="Pending" />
                  <Metric value={client.connected_integrations} label="Connected" />
                </div>

                <button
                  type="button"
                  onClick={() => openClient(client)}
                  disabled={loadingId === client.tenant_id}
                  className={cn(
                    'text-[11px] font-body px-3 py-2 rounded-sm transition-all active:scale-[0.97] disabled:opacity-40',
                    isActive
                      ? 'border border-brand-border text-brand-text bg-transparent hover:bg-brand-elevated'
                      : 'bg-brand-green text-black font-medium hover:bg-[#00a844]',
                  )}
                >
                  {loadingId === client.tenant_id ? '...' : isActive ? 'Acting as this client' : 'Open / Act as'}
                </button>
              </motion.div>
            )
          })}
        </motion.div>
      )}
    </motion.div>
  )
}
