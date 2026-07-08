'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { RunDrawer } from './RunDrawer'
import { useCanConfigure } from '@/lib/auth-client'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Tool {
  id: string
  type: string
  autonomy_level: 'auto' | 'approve'
  status: 'active' | 'inactive'
  version: number
  config_json?: Record<string, unknown>
  last_configured_by_email?: string | null
}

export function formatType(type: string): string {
  return type.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') + ' Tool'
}

function typeToSlug(type: string): string {
  return type.replace(/_/g, '-')
}

const AUTONOMY_BADGE: Record<Tool['autonomy_level'], { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-brand-green border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
}

interface Props {
  tool: Tool
  onConfigure: () => void
  onStatusChange: () => void
}

export function ToolCard({ tool, onConfigure, onStatusChange }: Props) {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const { toast } = useToast()
  const [toggling, setToggling]               = useState(false)
  const [confirmDelete, setConfirmDelete]     = useState(false)
  const [deleting, setDeleting]               = useState(false)
  const [showRun, setShowRun]                 = useState(false)
  const [lastExecutionId, setLastExecutionId] = useState<string | null>(null)

  const isActive = tool.status === 'active'
  const badge    = AUTONOMY_BADGE[tool.autonomy_level]

  async function handleToggle() {
    setToggling(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/tools/${tool.id}/pause`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      if (!res.ok) { toast('Failed to update tool status', 'error'); return }
      toast(isActive ? 'Tool paused' : 'Tool resumed', 'success')
      onStatusChange()
    } catch {
      toast('Failed to update tool status', 'error')
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/tools/${tool.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { toast('Failed to delete tool', 'error'); return }
      toast('Tool deleted', 'success')
      onStatusChange()
    } catch {
      toast('Failed to delete tool', 'error')
    } finally {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  return (
    <>
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link href={`/tools/${typeToSlug(tool.type)}`} className="text-sm font-body text-brand-text font-medium hover:text-brand-green transition-colors">
              {formatType(tool.type)}
            </Link>
            <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>
            <span className="text-[11px] font-body text-brand-muted">v{tool.version}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          <div className="flex items-center gap-1.5">
            {isActive ? (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-green opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-green" />
              </span>
            ) : (
              <span className="h-2 w-2 rounded-full bg-brand-muted" />
            )}
            <span className={`text-xs font-body ${isActive ? 'text-brand-green' : 'text-brand-muted'}`}>
              {isActive ? 'Active' : 'Inactive'}
            </span>
          </div>

          {canConfigure && (
            <button type="button" onClick={onConfigure} className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-2.5 py-1 transition-colors">
              Configure
            </button>
          )}

          <button type="button" onClick={() => setShowRun(true)} disabled={!isActive} className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-2.5 py-1 transition-colors disabled:opacity-50">Run</button>

          {canConfigure && (
            <button
              type="button"
              onClick={handleToggle}
              disabled={toggling}
              className={[
                'text-xs font-body rounded-sm px-2.5 py-1 transition-colors disabled:opacity-50',
                isActive
                  ? 'border border-brand-border text-brand-muted hover:text-brand-text hover:bg-brand-elevated'
                  : 'border border-brand-border text-brand-green hover:bg-brand-elevated',
              ].join(' ')}
            >
              {toggling ? '…' : isActive ? 'Pause' : 'Resume'}
            </button>
          )}

          {canConfigure && (
            confirmDelete ? (
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-body text-brand-muted">Delete?</span>
                <button type="button" onClick={handleDelete} disabled={deleting} className="text-xs font-body bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] hover:bg-[rgba(255,77,109,0.2)] rounded-sm px-2.5 py-1 transition-colors disabled:opacity-50">
                  {deleting ? '…' : 'Confirm'}
                </button>
                <button type="button" onClick={() => setConfirmDelete(false)} className="text-xs font-body border border-brand-border text-brand-muted hover:text-brand-text rounded-sm px-2.5 py-1 transition-colors">
                  Cancel
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => setConfirmDelete(true)} className="text-xs font-body text-brand-muted hover:text-[#ff4d6d] transition-colors px-1">
                Delete
              </button>
            )
          )}
        </div>
      </div>

    </div>

    {lastExecutionId && (
      <div className="mt-2 flex items-center gap-3 bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)] rounded-sm px-3 py-2">
        <span className="text-[11px] font-body text-brand-green">Queued - execution {lastExecutionId.slice(0, 8)}…</span>
        <Link href="/executions" className="text-[11px] font-body text-brand-green underline underline-offset-2">View</Link>
        <button type="button" onClick={() => setLastExecutionId(null)} className="ml-auto text-[#4a6a4a] hover:text-brand-muted text-xs leading-none">✕</button>
      </div>
    )}

    {showRun && (
      <RunDrawer
        tool={tool}
        onClose={() => setShowRun(false)}
        onQueued={(id) => { setLastExecutionId(id); setShowRun(false) }}
      />
    )}
  </>
  )
}
