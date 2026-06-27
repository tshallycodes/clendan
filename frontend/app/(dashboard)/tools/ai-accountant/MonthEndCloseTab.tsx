'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { CloseRunChecklist } from './CloseRunChecklist'
import { CloseRunBottlenecks } from './CloseRunBottlenecks'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function currentMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

interface SignOff {
  email: string
  signed_at: string
}

interface CloseTask {
  task_key: string
  label: string
  status: 'pending' | 'complete' | 'blocked'
  completed_at: string | null
  completed_by: string | null
  notes: string | null
}

interface CloseRun {
  id: string
  period: string
  status: 'open' | 'in_progress' | 'closed'
  tasks: CloseTask[]
  sign_offs: SignOff[]
  created_at: string
  closed_at: string | null
  closed_by_email: string | null
}

const RUN_STATUS_BADGE: Record<string, string> = {
  open: 'bg-[rgba(245,166,35,0.08)] text-[#f5a623] border border-[rgba(245,166,35,0.2)]',
  in_progress: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]',
  closed: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]',
}

interface Props {
  toolId: string | null
}

export function MonthEndCloseTab({ toolId }: Props) {
  const { getToken } = useAuth()
  const [period, setPeriod] = useState(currentMonth)
  const [run, setRun] = useState<CloseRun | null>(null)
  const [loading, setLoading] = useState(false)
  const [opening, setOpening] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRun = useCallback(async (p: string) => {
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/close-runs`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Failed to load close runs')
      const json = await res.json()
      const runs: CloseRun[] = json.data?.runs ?? []
      setRun(runs.find((r) => r.period === p) ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error loading data')
    } finally {
      setLoading(false)
    }
  }, [getToken])

  useEffect(() => { fetchRun(period) }, [period, fetchRun])

  async function handleOpen() {
    setOpening(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/close-runs`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period }),
      })
      const json = await res.json()
      if (!res.ok) { setError(json.detail ?? 'Failed to open run'); return }
      setRun(json.data)
    } finally {
      setOpening(false)
    }
  }

  async function handleRefresh() {
    if (!run) return
    setRefreshing(true)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/close-runs/${run.id}/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      setTimeout(() => fetchRun(period), 2000)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleCompleteTask(taskKey: string) {
    if (!run) return
    const token = await getToken()
    const res = await fetch(`${API}/v1/close-runs/${run.id}/task/${taskKey}/complete`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (res.ok) { const j = await res.json(); setRun(j.data) }
  }

  async function handleSignOff() {
    if (!run) return
    const token = await getToken()
    const res = await fetch(`${API}/v1/close-runs/${run.id}/sign-off`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) { const j = await res.json(); setRun(j.data) }
  }

  return (
    <div className="space-y-4">
      {/* Period picker + action */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Period</label>
          <input
            type="month"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text font-mono text-xs rounded-sm px-3 py-1.5 outline-none"
          />
        </div>
        {!loading && !run && (
          <button
            type="button"
            onClick={handleOpen}
            disabled={opening}
            className="mt-5 bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] text-xs font-mono rounded-sm px-4 py-1.5 transition-all disabled:opacity-50"
          >
            {opening ? 'Opening…' : 'Open Close Run'}
          </button>
        )}
        {run && (
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing || run.status === 'closed'}
            className="mt-5 text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors disabled:opacity-50"
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        )}
      </div>

      {error && (
        <p className="text-xs font-mono text-[#ff4d6d]">{error}</p>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 animate-pulse bg-brand-elevated rounded-sm" />
          ))}
        </div>
      )}

      {/* No run for period */}
      {!loading && !run && !error && (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-6 text-center">
          <p className="text-xs font-mono text-brand-muted">
            No close run for {period}. Open one to begin the month-end checklist.
          </p>
        </div>
      )}

      {/* Run detail */}
      <AnimatePresence mode="wait">
        {!loading && run && (
          <motion.div
            key={run.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="space-y-4"
          >
            {/* Status badge */}
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${RUN_STATUS_BADGE[run.status] ?? ''}`}>
                {run.status.replace('_', ' ').toUpperCase()}
              </span>
              <span className="text-[10px] font-mono text-brand-muted">Period {run.period}</span>
            </div>

            <CloseRunChecklist
              tasks={run.tasks}
              onCompleteTask={handleCompleteTask}
              runClosed={run.status === 'closed'}
            />

            <CloseRunSignOffs
              signOffs={run.sign_offs}
              onSignOff={handleSignOff}
              runClosed={run.status === 'closed'}
            />

            <CloseRunBottlenecks runId={run.id} tasks={run.tasks} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

interface SignOffsProps {
  signOffs: SignOff[]
  onSignOff: () => void
  runClosed: boolean
}

function CloseRunSignOffs({ signOffs, onSignOff, runClosed }: SignOffsProps) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-brand-border flex items-center justify-between">
        <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Sign-offs</p>
        {!runClosed && (
          <button
            type="button"
            onClick={onSignOff}
            className="text-[10px] font-mono bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1 transition-all"
          >
            Sign Off
          </button>
        )}
      </div>
      {signOffs.length === 0 ? (
        <p className="px-4 py-4 text-xs font-mono text-brand-muted">No sign-offs yet.</p>
      ) : (
        <div className="divide-y divide-brand-border">
          {signOffs.map((s) => (
            <div key={s.email} className="px-4 py-2.5 flex items-center justify-between">
              <span className="text-xs font-mono text-brand-text">{s.email}</span>
              <span className="text-[10px] font-mono text-brand-muted">
                {new Date(s.signed_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
