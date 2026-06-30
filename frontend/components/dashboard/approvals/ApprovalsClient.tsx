'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { StatusBadge } from '@/components/dashboard/StatusBadge'
import { cn } from '@/lib/utils'
import { useCanApprove } from '@/lib/auth-client'
import { useToast } from '@/components/Providers'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Approval {
  id: string
  execution_id: string
  status: string
  requested_at: string
  expires_at: string
  decision: string | null
  confidence: number | null
}

type Tab = 'all' | 'pending' | 'approved' | 'rejected'

const TABS: { key: Tab; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
]


function getExpiryDisplay(expiresAt: string): { label: string; urgent: boolean } {
  const now = Date.now()
  const diff = new Date(expiresAt).getTime() - now
  if (diff <= 0) return { label: 'Expired', urgent: true }
  const hours = Math.floor(diff / 3_600_000)
  const minutes = Math.floor((diff % 3_600_000) / 60_000)
  if (diff < 7_200_000) {
    return { label: `Expires in ${hours}h ${minutes}m`, urgent: true }
  }
  return {
    label: `Expires ${new Date(expiresAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}`,
    urgent: false,
  }
}

function getWaitingLabel(requestedAt: string): string {
  const diffMs = Date.now() - new Date(requestedAt).getTime()
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 60) return `Waiting ${minutes}m`
  const hours = Math.floor(minutes / 60)
  return `Waiting ${hours}h ${minutes % 60}m`
}

interface TraceCardProps {
  approval: Approval
  onClose: () => void
}

function TracePanel({ approval, onClose }: TraceCardProps) {
  const traceData = {
    execution_id: approval.execution_id,
    decision: approval.decision,
    confidence: approval.confidence,
    requested_at: approval.requested_at,
    expires_at: approval.expires_at,
  }
  return (
    <div className="mt-3 bg-brand-bg border border-brand-border rounded-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Execution Trace</span>
        <button
          onClick={onClose}
          className="text-[11px] font-body text-brand-muted hover:text-brand-text transition-colors"
        >
          Close
        </button>
      </div>
      <pre className="text-[12px] font-body text-brand-secondary whitespace-pre-wrap break-all">
        {JSON.stringify(traceData, null, 2)}
      </pre>
    </div>
  )
}

interface ApprovalCardProps {
  approval: Approval
  onAction: (id: string, action: 'approve' | 'reject') => Promise<void>
  loadingState: 'approve' | 'reject' | null
}

function PendingCard({ approval, onAction, loadingState }: ApprovalCardProps) {
  const [traceOpen, setTraceOpen] = useState(false)
  const canApprove = useCanApprove()
  const expiry = getExpiryDisplay(approval.expires_at)
  const waiting = getWaitingLabel(approval.requested_at)

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center gap-3">
            <span className="text-sm font-body text-brand-text">
              Approval #{approval.id.slice(-6)}
            </span>
            <span
              className={cn(
                'text-[11px] font-body',
                expiry.urgent ? 'text-[#f5a623]' : 'text-brand-muted',
              )}
            >
              {expiry.label}
            </span>
          </div>
          <div className="text-[11px] font-body text-brand-muted">{waiting}</div>
          {approval.decision && (
            <div className="text-xs font-body text-brand-secondary capitalize">
              Decision: {approval.decision}
            </div>
          )}
          {approval.confidence != null && (
            <div className="text-[11px] font-body text-brand-muted">
              Confidence: {(approval.confidence * 100).toFixed(0)}%
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          {canApprove && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onAction(approval.id, 'approve')}
                disabled={loadingState !== null}
                className="text-[11px] font-body px-3 py-1.5 bg-brand-green text-black font-medium hover:bg-[#00a844] active:scale-[0.97] transition-all rounded-sm disabled:opacity-40"
              >
                {loadingState === 'approve' ? '...' : 'Approve'}
              </button>
              <button
                type="button"
                onClick={() => onAction(approval.id, 'reject')}
                disabled={loadingState !== null}
                className="text-[11px] font-body px-3 py-1.5 border border-[#ff4d6d] text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.12)] active:scale-[0.97] transition-all rounded-sm disabled:opacity-40"
              >
                {loadingState === 'reject' ? '...' : 'Reject'}
              </button>
            </div>
          )}
          <button
            type="button"
            onClick={() => setTraceOpen((v) => !v)}
            className="text-[11px] font-body text-brand-muted hover:text-brand-text transition-colors"
          >
            View trace →
          </button>
        </div>
      </div>
      {traceOpen && (
        <TracePanel approval={approval} onClose={() => setTraceOpen(false)} />
      )}
    </div>
  )
}

function ResolvedCard({ approval }: { approval: Approval }) {
  const [traceOpen, setTraceOpen] = useState(false)
  const resolvedAt = new Date(approval.expires_at).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center gap-3">
            <span className="text-sm font-body text-brand-text">
              Approval #{approval.id.slice(-6)}
            </span>
            <StatusBadge status={approval.status === 'approved' ? 'auto' : 'blocked'} />
          </div>
          <div className="text-[11px] font-body text-brand-muted">{resolvedAt}</div>
          {approval.decision && (
            <div className="text-xs font-body text-brand-secondary capitalize">
              Decision: {approval.decision}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={() => setTraceOpen((v) => !v)}
          className="text-[11px] font-body text-brand-muted hover:text-brand-text transition-colors self-start"
        >
          View trace →
        </button>
      </div>
      {traceOpen && (
        <TracePanel approval={approval} onClose={() => setTraceOpen(false)} />
      )}
    </div>
  )
}

const pageVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}
const cardListVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
}
const cardVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}

interface Props {
  initialApprovals: Approval[]
}

export function ApprovalsClient({ initialApprovals }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [approvals, setApprovals] = useState<Approval[]>(initialApprovals)
  const [activeTab, setActiveTab] = useState<Tab>('pending')
  const [loadingMap, setLoadingMap] = useState<Record<string, 'approve' | 'reject' | null>>({})

  async function handleAction(id: string, action: 'approve' | 'reject') {
    setLoadingMap((prev) => ({ ...prev, [id]: action }))
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(`${API_BASE}/approvals/${id}/respond`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      if (res.ok) {
        setApprovals((prev) =>
          prev.map((a) =>
            a.id === id ? { ...a, status: action === 'approve' ? 'approved' : 'rejected' } : a,
          ),
        )
        toast(action === 'approve' ? 'Approval approved' : 'Approval rejected', action === 'approve' ? 'success' : 'info')
      } else {
        toast('Action failed — try again', 'error')
      }
    } finally {
      setLoadingMap((prev) => ({ ...prev, [id]: null }))
    }
  }

  const filtered = approvals.filter((a) => {
    if (activeTab === 'all') return true
    if (activeTab === 'pending') return a.status === 'pending'
    if (activeTab === 'approved') return a.status === 'approved'
    if (activeTab === 'rejected') return a.status === 'rejected'
    return true
  })

  const pendingCount = approvals.filter((a) => a.status === 'pending').length

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-6">
      <motion.div variants={sectionVariants}>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Approval Queue</h1>
        <p className="text-brand-muted text-xs font-body mt-1">
          {pendingCount} pending {pendingCount === 1 ? 'approval' : 'approvals'}
        </p>
      </motion.div>

      <motion.div variants={sectionVariants} className="flex gap-1">
        {TABS.map((tab) => (
          <button
            type="button"
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'text-[11px] font-body px-3 py-1.5 rounded-sm border transition-colors tracking-wider uppercase',
              activeTab === tab.key
                ? 'border-brand-green/30 bg-brand-green/10 text-brand-green'
                : 'border-brand-border bg-transparent text-brand-muted hover:text-brand-text',
            )}
          >
            {tab.label}
          </button>
        ))}
      </motion.div>

      {filtered.length === 0 && activeTab === 'pending' ? (
        <motion.div variants={sectionVariants} className="bg-brand-surface border border-brand-border rounded-sm p-12 flex flex-col items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-brand-green animate-pulse" />
            <p className="text-xs font-body text-brand-muted">
              No pending approvals — tools are executing autonomously
            </p>
          </div>
        </motion.div>
      ) : filtered.length === 0 ? (
        <motion.div variants={sectionVariants} className="bg-brand-surface border border-brand-border rounded-sm p-12 text-center">
          <p className="text-xs font-body text-brand-muted">No approvals in this category</p>
        </motion.div>
      ) : (
        <motion.div variants={cardListVariants} className="space-y-3">
          {filtered.map((approval) => (
            <motion.div key={approval.id} variants={cardVariants}>
              {approval.status === 'pending' ? (
                <PendingCard
                  approval={approval}
                  onAction={handleAction}
                  loadingState={loadingMap[approval.id] ?? null}
                />
              ) : (
                <ResolvedCard approval={approval} />
              )}
            </motion.div>
          ))}
        </motion.div>
      )}
    </motion.div>
  )
}
