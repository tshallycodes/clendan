'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { useToast } from '@/components/Providers'
import { motion, AnimatePresence } from 'framer-motion'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import { slugToTool, INTEGRATION_CATEGORY_LABELS, type ToolDef } from '@/app/(dashboard)/tools/tools-data'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface LatestExecution {
  id: string
  status: string
  decision: string
  confidence: number
  duration_ms: number | null
  error: string | null
  triggered_by_email: string | null
  created_at: string
}

export interface ToolRenderCtx {
  deployed: Tool | null
  trace: Record<string, unknown> | null
  execution: LatestExecution | null
  loading: boolean
  running: boolean
  refresh: () => void
}

interface Props {
  toolSlug: string
  runLabel?: string
  /** Extra controls rendered inline with the Run button (e.g. period pickers). */
  runControls?: React.ReactNode
  /** Payload sent to POST /tools/{id}/run. */
  buildRunPayload?: () => Record<string, unknown>
  children: (ctx: ToolRenderCtx) => React.ReactNode
}

const AUTONOMY_BADGE: Record<string, { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
}
const AUTONOMY_DESC: Record<string, string> = {
  auto:    'Executes automatically — no approval required before acting.',
  approve: 'Every decision is routed to you for review before the agent acts.',
}
const DEFAULT_HOW_IT_WORKS = [
  { step: '01', label: 'Trigger',      desc: 'Runs on a schedule, an incoming event, or when you click Run. Data is pulled from your connected integrations.' },
  { step: '02', label: 'Execute',      desc: 'The agent processes the data using your configured rules and AI reasoning.' },
  { step: '03', label: 'Policy check', desc: 'Every output is validated by the policy engine before any action is taken. Cannot be skipped.' },
  { step: '04', label: 'Audit',        desc: 'The full decision and reasoning trace is written to the immutable audit log before returning.' },
]

const pageVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const EASE = [0.25, 0.46, 0.45, 0.94] as const
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: EASE } },
}

const POLL_MS = 3000
const POLL_TIMEOUT_MS = 5 * 60 * 1000

export function ToolPageShell({ toolSlug, runLabel = 'Run now', runControls, buildRunPayload, children }: Props) {
  const tool = slugToTool(toolSlug) as ToolDef
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const { toast } = useToast()

  const [deployed, setDeployed] = useState<Tool | null>(null)
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null)
  const [execution, setExecution] = useState<LatestExecution | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [showConfig, setShowConfig] = useState(false)
  const [showOverview, setShowOverview] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchDeployed = useCallback(async (): Promise<Tool | null> => {
    const token = await getToken()
    const res = await fetch(`${API}/tools`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return null
    const json = await res.json()
    const tools: Tool[] = json.data?.tools ?? json.data ?? []
    const found = tools.find((t) => t.type === tool.type) ?? null
    setDeployed(found)
    return found
  }, [getToken, tool.type])

  const fetchResult = useCallback(async (toolId: string) => {
    const token = await getToken()
    const res = await fetch(`${API}/tools/${toolId}/latest-result`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return null
    const json = await res.json()
    const data = json.data as { execution: LatestExecution | null; reasoning_trace: Record<string, unknown> | null }
    setExecution(data.execution)
    setTrace(data.reasoning_trace)
    return data.execution
  }, [getToken])

  const refresh = useCallback(async () => {
    const d = await fetchDeployed()
    if (d) await fetchResult(d.id)
  }, [fetchDeployed, fetchResult])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      const d = await fetchDeployed()
      if (!cancelled && d) await fetchResult(d.id)
      if (!cancelled) setLoading(false)
    })()
    return () => {
      cancelled = true
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchDeployed, fetchResult])

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  async function runTool() {
    if (!deployed || running) return
    setRunning(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/tools/${deployed.id}/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: buildRunPayload?.() ?? {} }),
      })
      if (!res.ok) {
        const j = await res.json().catch(() => null)
        toast(j?.detail ?? 'Could not start the run', 'error')
        setRunning(false)
        return
      }
      const { execution_id } = (await res.json()).data as { execution_id: string }
      toast('Run started — processing…', 'success')

      const startedAt = Date.now()
      stopPolling()
      pollRef.current = setInterval(async () => {
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          stopPolling(); setRunning(false)
          toast('Run is taking longer than expected — check back shortly', 'error')
          return
        }
        const exec = await fetchResult(deployed.id)
        if (exec && exec.id === execution_id && (exec.status === 'completed' || exec.status === 'failed')) {
          stopPolling(); setRunning(false)
          if (exec.status === 'failed') toast('Run failed — see the audit trail', 'error')
          else toast('Run complete', 'success')
        }
      }, POLL_MS)
    } catch {
      toast('Network error', 'error')
      setRunning(false)
    }
  }

  async function handleToggle() {
    if (!deployed) return
    setToggling(true)
    try {
      const token = await getToken()
      await fetch(`${API}/tools/${deployed.id}/pause`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      const d = await fetchDeployed()
      toast(d?.status === 'active' ? 'Tool resumed' : 'Tool paused', 'success')
    } finally {
      setToggling(false)
    }
  }

  async function handleDeploy() {
    setDeploying(true)
    try {
      const token = await getToken()
      const { getDefaultConfig } = await import('@/components/dashboard/tools/ToolConfigFields')
      const res = await fetch(`${API}/tools`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: tool.type, autonomy_level: 'approve', config: getDefaultConfig(tool.type) }),
      })
      if (res.ok) toast('Tool deployed', 'success')
      else toast('Deploy failed', 'error')
      await fetchDeployed()
    } finally {
      setDeploying(false)
    }
  }

  const isActive = deployed?.status === 'active'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.approve) : null
  const actionLoading = toggling || deploying

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-6">
      <motion.div variants={sectionVariants}>
        <Link href="/tools" className="text-[12px] font-body text-brand-muted hover:text-brand-secondary transition-colors">
          &larr; Tools
        </Link>
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-heading font-bold text-2xl text-brand-text">{tool.name}</h1>
            {badge && <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>}
          </div>
          <p className="text-xs font-body text-brand-muted max-w-xl">{tool.desc}</p>
        </div>

        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setShowOverview(true)}
            className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors">
            Overview
          </button>
          {canConfigure && (
            <>
              <button type="button" onClick={() => setShowConfig(true)}
                className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors">
                Configure
              </button>
              <button type="button" onClick={isActive ? handleToggle : handleDeploy} disabled={actionLoading}
                className={`text-xs font-body rounded-sm px-3 py-1.5 transition-all disabled:opacity-50 ${
                  isActive
                    ? 'border border-brand-border text-brand-text hover:bg-brand-elevated'
                    : 'bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97]'
                }`}>
                {toggling ? 'Pausing…' : deploying ? 'Deploying…' : isActive ? 'Pause' : 'Deploy'}
              </button>
            </>
          )}
        </div>
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          {isActive ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00C853]" />
              </span>
              <span className="text-xs font-body text-[#00C853]">Active</span>
            </>
          ) : (
            <>
              <span className="h-2 w-2 rounded-full bg-brand-muted" />
              <span className="text-xs font-body text-brand-muted">{deployed ? 'Paused' : 'Not deployed'}</span>
            </>
          )}
          {execution?.created_at && (
            <span className="text-[11px] font-body text-brand-muted ml-2">
              Last run {new Date(execution.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>

        {isActive && canConfigure && (
          <div className="flex items-center gap-2">
            {runControls}
            <button
              type="button"
              onClick={runTool}
              disabled={running}
              className="text-xs font-body bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-1.5 transition-all disabled:opacity-50"
            >
              {running ? 'Running…' : runLabel}
            </button>
          </div>
        )}
      </motion.div>

      {/* Tool-specific result body */}
      <motion.div variants={sectionVariants}>
        {children({ deployed, trace, execution, loading, running, refresh })}
      </motion.div>

      {/* Overview Sidebar */}
      <AnimatePresence>
        {showOverview && (
          <div className="fixed inset-0 z-40 flex justify-end">
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
              className="absolute inset-0 bg-black/40" onClick={() => setShowOverview(false)}
            />
            <motion.div
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="relative h-screen w-[400px] bg-brand-surface border-l border-brand-border p-6 overflow-y-auto shadow-2xl z-50 flex flex-col"
            >
              <div className="flex items-center justify-between mb-6 shrink-0">
                <h2 className="font-heading font-semibold text-brand-text text-sm">Overview</h2>
                <button type="button" onClick={() => setShowOverview(false)} className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none">✕</button>
              </div>

              <div className="space-y-6 flex-1">
                <div className="bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
                  <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Requires</p>
                  <p className="text-xs font-body text-brand-secondary mt-1">
                    {tool.requires.length
                      ? tool.requires.map((c) => INTEGRATION_CATEGORY_LABELS[c]).join(' · ')
                      : 'No integration — runs on upload or manual trigger'}
                  </p>
                </div>

                <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">How it works</p>
                  </div>
                  <div className="divide-y divide-brand-border">
                    {(tool.howItWorks ?? DEFAULT_HOW_IT_WORKS).map(({ step, label, desc }) => (
                      <div key={step} className="px-4 py-3 flex gap-4">
                        <p className="text-[11px] font-body text-brand-muted font-mono">{step}</p>
                        <div>
                          <p className="text-xs font-body font-medium text-brand-text">{label}</p>
                          <p className="text-[11px] font-body text-brand-muted leading-relaxed mt-0.5">{desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {deployed && (
                  <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                    <div className="px-4 py-3 border-b border-brand-border">
                      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Configuration</p>
                    </div>
                    <div className="px-4 py-4 space-y-4">
                      <div className="space-y-1.5">
                        <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Autonomy</p>
                        {badge && <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm inline-block ${badge.className}`}>{badge.label}</span>}
                        <p className="text-[11px] font-body text-brand-muted leading-relaxed">{AUTONOMY_DESC[deployed.autonomy_level] ?? ''}</p>
                      </div>
                      <div className="space-y-1.5">
                        <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Status</p>
                        <p className="text-xs font-body text-brand-text">{deployed.status === 'active' ? 'Running' : 'Paused'}</p>
                      </div>
                    </div>
                  </div>
                )}

                <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Capabilities</p>
                  </div>
                  <ul className="divide-y divide-brand-border">
                    {tool.capabilities.map((cap) => (
                      <li key={cap} className="flex items-start gap-3 px-4 py-3">
                        <span className="text-brand-muted font-body text-[11px] mt-0.5 shrink-0">→</span>
                        <span className="text-xs font-body text-brand-secondary">{cap}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {showConfig && (
        <ConfigDrawer
          tool={deployed}
          toolType={tool.type}
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); refresh() }}
        />
      )}
    </motion.div>
  )
}

/** Placeholder shown by a tool body when there is no result yet. */
export function ToolResultState({ deployed, loading, notDeployedHint }: {
  deployed: Tool | null
  loading: boolean
  notDeployedHint?: string
}) {
  if (!deployed) {
    return (
      <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-16 text-center">
        <p className="text-xs font-body text-brand-secondary">This agent is not deployed yet.</p>
        <p className="text-[11px] font-body text-brand-muted mt-1">{notDeployedHint ?? 'Deploy it to start processing and see results here.'}</p>
      </div>
    )
  }
  if (loading) {
    return <div className="h-40 bg-brand-elevated rounded-sm animate-pulse" />
  }
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-16 text-center">
      <p className="text-xs font-body text-brand-muted">No results yet — click Run to process your latest data.</p>
    </div>
  )
}
