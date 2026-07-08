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
  tool_type: string | null
  triggered_by: string | null
  document_filename: string | null
  document_type: string | null
  reason: string | null
  rule_triggered: string | null
  reasoning: string | null
}

type Tab = 'all' | 'pending' | 'approved' | 'rejected'

const TABS: { key: Tab; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
]

/** Left-accent colour per approval status, following the Tool Card pattern. */
function accentClass(status: string): string {
  if (status === 'approved') return 'border-l-brand-green'
  if (status === 'rejected') return 'border-l-[#ff4d6d]'
  return 'border-l-[#00a8cc]' // pending
}

function toToolLabel(type: string | null): string {
  if (!type) return 'Approval'
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Best available one-line human explanation of why this needs a human. */
function summaryLine(a: Approval): string {
  return a.reason || a.reasoning || a.rule_triggered || 'Awaiting manual review'
}

function formatTs(iso: string): string {
  const d = new Date(iso)
  return (
    d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) +
    ' ' +
    d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  )
}

function getExpiryDisplay(expiresAt: string): { label: string; urgent: boolean } {
  const diff = new Date(expiresAt).getTime() - Date.now()
  if (diff <= 0) return { label: 'Expired', urgent: true }
  const hours = Math.floor(diff / 3_600_000)
  const minutes = Math.floor((diff % 3_600_000) / 60_000)
  if (diff < 7_200_000) return { label: `Expires in ${hours}h ${minutes}m`, urgent: true }
  return {
    label: `Expires ${new Date(expiresAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}`,
    urgent: false,
  }
}

function getWaitingLabel(requestedAt: string): string {
  const minutes = Math.floor((Date.now() - new Date(requestedAt).getTime()) / 60_000)
  if (minutes < 60) return `Waiting ${minutes}m`
  const hours = Math.floor(minutes / 60)
  return `Waiting ${hours}h ${minutes % 60}m`
}

interface ActionProps {
  onAction: (id: string, action: 'approve' | 'reject') => Promise<void>
  loadingState: 'approve' | 'reject' | null
}

function ActionButtons({
  approvalId,
  onAction,
  loadingState,
  full,
}: ActionProps & { approvalId: string; full?: boolean }) {
  return (
    <div className={cn('flex gap-2', full && 'w-full')}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onAction(approvalId, 'approve')
        }}
        disabled={loadingState !== null}
        className={cn(
          'text-[11px] font-body px-3 py-1.5 bg-brand-green text-black font-medium hover:bg-[#00a844] active:scale-[0.97] transition-all rounded-sm disabled:opacity-40',
          full && 'flex-1 py-2',
        )}
      >
        {loadingState === 'approve' ? '...' : 'Approve'}
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onAction(approvalId, 'reject')
        }}
        disabled={loadingState !== null}
        className={cn(
          'text-[11px] font-body px-3 py-1.5 border border-[#ff4d6d] text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.12)] active:scale-[0.97] transition-all rounded-sm disabled:opacity-40',
          full && 'flex-1 py-2',
        )}
      >
        {loadingState === 'reject' ? '...' : 'Reject'}
      </button>
    </div>
  )
}

interface CardProps extends ActionProps {
  approval: Approval
  onOpen: () => void
}

function ApprovalCard({ approval, onOpen, onAction, loadingState }: CardProps) {
  const canApprove = useCanApprove()
  const isPending = approval.status === 'pending'
  const expiry = getExpiryDisplay(approval.expires_at)

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'w-full text-left bg-brand-surface border border-brand-border border-l-[3px] rounded-sm p-4 hover:bg-brand-elevated transition-colors',
        accentClass(approval.status),
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center gap-2.5">
            <span className="text-sm font-heading font-semibold text-brand-text truncate">
              {toToolLabel(approval.tool_type)}
            </span>
            {!isPending && (
              <StatusBadge status={approval.status === 'approved' ? 'auto' : 'blocked'} />
            )}
          </div>

          {approval.document_filename && (
            <div className="text-xs font-body text-brand-secondary truncate">
              {approval.document_filename}
              {approval.document_type && (
                <span className="text-brand-muted"> · {approval.document_type}</span>
              )}
            </div>
          )}

          <div className="text-xs font-body text-brand-muted line-clamp-2">
            {summaryLine(approval)}
          </div>

          <div className="flex items-center gap-3 pt-0.5">
            {approval.confidence != null && (
              <span className="text-[11px] font-body text-brand-muted">
                Confidence {(approval.confidence * 100).toFixed(0)}%
              </span>
            )}
            {approval.triggered_by && (
              <span className="text-[11px] font-body text-brand-muted">
                by {approval.triggered_by}
              </span>
            )}
            <span className="text-[11px] font-body text-brand-muted">
              {isPending ? getWaitingLabel(approval.requested_at) : formatTs(approval.requested_at)}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0">
          {isPending && (
            <span
              className={cn(
                'text-[11px] font-body whitespace-nowrap',
                expiry.urgent ? 'text-[#f5a623]' : 'text-brand-muted',
              )}
            >
              {expiry.label}
            </span>
          )}
          {isPending && canApprove && (
            <ActionButtons approvalId={approval.id} onAction={onAction} loadingState={loadingState} />
          )}
          <span className="text-[11px] font-body text-brand-muted">Details →</span>
        </div>
      </div>
    </button>
  )
}

interface DrawerProps extends ActionProps {
  approval: Approval
  onClose: () => void
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1">{label}</div>
      <div className="text-sm font-body text-brand-text">{value}</div>
    </div>
  )
}

function ApprovalDrawer({ approval, onClose, onAction, loadingState }: DrawerProps) {
  const canApprove = useCanApprove()
  const isPending = approval.status === 'pending'
  const expiry = getExpiryDisplay(approval.expires_at)
  const summary = summaryLine(approval)

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-screen w-96 bg-brand-surface border-l border-brand-border p-6 z-50 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <span className="text-xs font-body text-brand-muted uppercase tracking-widest">
            Approval Detail
          </span>
          <button
            onClick={onClose}
            className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        <div className="space-y-5">
          <div className="flex items-center gap-2.5">
            <span className="text-base font-heading font-bold text-brand-text">
              {toToolLabel(approval.tool_type)}
            </span>
            <StatusBadge
              status={
                approval.status === 'approved'
                  ? 'auto'
                  : approval.status === 'rejected'
                    ? 'blocked'
                    : 'pending'
              }
            />
          </div>

          {approval.document_filename && (
            <DetailRow
              label="Document"
              value={
                <span className="break-all">
                  {approval.document_filename}
                  {approval.document_type && (
                    <span className="text-brand-muted"> · {approval.document_type}</span>
                  )}
                </span>
              }
            />
          )}

          <div>
            <div className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-1">
              Why this needs review
            </div>
            <div className="text-sm font-body text-brand-secondary leading-relaxed">{summary}</div>
            {approval.rule_triggered && approval.rule_triggered !== summary && (
              <div className="mt-2 inline-block text-[11px] font-body text-[#f5a623] bg-[rgba(245,166,35,0.08)] border border-[rgba(245,166,35,0.2)] rounded-sm px-2 py-0.5">
                {approval.rule_triggered}
              </div>
            )}
          </div>

          {approval.decision && (
            <DetailRow
              label="Decision"
              value={
                <span className="capitalize">
                  {approval.decision.replace(/_/g, ' ')}
                  {approval.confidence != null && (
                    <span className="text-[11px] text-brand-muted ml-2 normal-case">
                      {(approval.confidence * 100).toFixed(0)}% confidence
                    </span>
                  )}
                </span>
              }
            />
          )}

          {approval.triggered_by && <DetailRow label="Triggered by" value={approval.triggered_by} />}

          <DetailRow label="Requested" value={formatTs(approval.requested_at)} />

          {isPending && (
            <DetailRow
              label="Expiry"
              value={
                <span className={expiry.urgent ? 'text-[#f5a623]' : undefined}>{expiry.label}</span>
              }
            />
          )}

          {isPending && canApprove && (
            <div className="pt-2 border-t border-brand-border">
              <div className="text-[11px] font-body text-brand-muted uppercase tracking-widest mb-3">
                Actions
              </div>
              <ActionButtons
                approvalId={approval.id}
                onAction={onAction}
                loadingState={loadingState}
                full
              />
            </div>
          )}
        </div>
      </div>
    </>
  )
}

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

interface Props {
  initialApprovals: Approval[]
}

export function ApprovalsClient({ initialApprovals }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [approvals, setApprovals] = useState<Approval[]>(initialApprovals)
  const [activeTab, setActiveTab] = useState<Tab>('pending')
  const [selectedId, setSelectedId] = useState<string | null>(null)
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
        toast(
          action === 'approve' ? 'Approval approved' : 'Approval rejected',
          action === 'approve' ? 'success' : 'info',
        )
      } else {
        toast('Action failed - try again', 'error')
      }
    } finally {
      setLoadingMap((prev) => ({ ...prev, [id]: null }))
    }
  }

  const filtered = approvals.filter((a) => activeTab === 'all' || a.status === activeTab)
  const pendingCount = approvals.filter((a) => a.status === 'pending').length
  const selected = approvals.find((a) => a.id === selectedId) ?? null

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
        <motion.div
          variants={sectionVariants}
          className="bg-brand-surface border border-brand-border rounded-sm p-12 flex flex-col items-center gap-3"
        >
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-brand-green animate-pulse" />
            <p className="text-xs font-body text-brand-muted">
              No pending approvals - tools are executing autonomously
            </p>
          </div>
        </motion.div>
      ) : filtered.length === 0 ? (
        <motion.div
          variants={sectionVariants}
          className="bg-brand-surface border border-brand-border rounded-sm p-12 text-center"
        >
          <p className="text-xs font-body text-brand-muted">No approvals in this category</p>
        </motion.div>
      ) : (
        <motion.div variants={cardListVariants} className="space-y-3">
          {filtered.map((approval) => (
            <motion.div key={approval.id} variants={cardVariants}>
              <ApprovalCard
                approval={approval}
                onOpen={() => setSelectedId(approval.id)}
                onAction={handleAction}
                loadingState={loadingMap[approval.id] ?? null}
              />
            </motion.div>
          ))}
        </motion.div>
      )}

      {selected && (
        <ApprovalDrawer
          approval={selected}
          onClose={() => setSelectedId(null)}
          onAction={handleAction}
          loadingState={loadingMap[selected.id] ?? null}
        />
      )}
    </motion.div>
  )
}
