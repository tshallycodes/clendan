'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { WorkerTestResult } from './WorkerTestResult'
import { useRunTest } from './useRunTest'
import { useCanConfigure } from '@/lib/auth-client'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Worker {
  id: string
  type: string
  autonomy_level: 'auto' | 'approve' | 'suggest'
  status: 'active' | 'inactive'
  version: number
  config_json?: Record<string, unknown>
}

export function formatType(type: string): string {
  return type.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') + ' Worker'
}

const AUTONOMY_BADGE: Record<Worker['autonomy_level'], { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-brand-green border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
  suggest: { label: 'Suggest', className: 'bg-brand-surface text-brand-muted border border-brand-border' },
}

interface Props {
  worker: Worker
  onConfigure: () => void
  onStatusChange: () => void
}

export function WorkerCard({ worker, onConfigure, onStatusChange }: Props) {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const [toggling, setToggling]           = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting]           = useState(false)
  const { run, running, result, dismiss } = useRunTest(worker.id, worker.type)

  const isActive = worker.status === 'active'
  const badge    = AUTONOMY_BADGE[worker.autonomy_level]

  async function handleToggle() {
    setToggling(true)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/workers/${worker.id}/pause`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      onStatusChange()
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/workers/${worker.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      onStatusChange()
    } finally {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  return (
    <div className={[
      'bg-brand-surface border border-brand-border rounded-sm p-4',
      isActive ? 'border-l-[3px] border-l-brand-green' : 'border-l-[3px] border-l-brand-muted',
    ].join(' ')}>
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link href={`/dashboard/workers/${worker.id}`} className="text-sm font-mono text-brand-text font-medium hover:text-brand-green transition-colors">
              {formatType(worker.type)}
            </Link>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>
            <span className="text-[10px] font-mono text-brand-muted">v{worker.version}</span>
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
            <span className={`text-xs font-mono ${isActive ? 'text-brand-green' : 'text-brand-muted'}`}>
              {isActive ? 'Active' : 'Inactive'}
            </span>
          </div>

          {canConfigure && (
            <button type="button" onClick={onConfigure} className="text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-2.5 py-1 transition-colors">
              Configure
            </button>
          )}

          <button type="button" onClick={run} disabled={running} className="text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-2.5 py-1 transition-colors disabled:opacity-50">
            {running ? 'Running…' : 'Run test'}
          </button>

          {canConfigure && (
            <button
              type="button"
              onClick={handleToggle}
              disabled={toggling}
              className={[
                'text-xs font-mono rounded-sm px-2.5 py-1 transition-colors disabled:opacity-50',
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
                <span className="text-[10px] font-mono text-brand-muted">Delete?</span>
                <button type="button" onClick={handleDelete} disabled={deleting} className="text-xs font-mono bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d] hover:bg-[rgba(255,77,109,0.2)] rounded-sm px-2.5 py-1 transition-colors disabled:opacity-50">
                  {deleting ? '…' : 'Confirm'}
                </button>
                <button type="button" onClick={() => setConfirmDelete(false)} className="text-xs font-mono border border-brand-border text-brand-muted hover:text-brand-text rounded-sm px-2.5 py-1 transition-colors">
                  Cancel
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => setConfirmDelete(true)} className="text-xs font-mono text-brand-muted hover:text-[#ff4d6d] transition-colors px-1">
                Delete
              </button>
            )
          )}
        </div>
      </div>

      {result && <WorkerTestResult result={result} onDismiss={dismiss} />}
    </div>
  )
}
