'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { useToast } from '@/components/Providers'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import { ToolExecutionsTab } from '@/components/dashboard/tools/ToolExecutionsTab'
import { ToolApprovalsTab } from '@/components/dashboard/tools/ToolApprovalsTab'
import { ToolAuditTab } from '@/components/dashboard/tools/ToolAuditTab'
import { CloseRunChecklist } from './CloseRunChecklist'
import { CloseRunBottlenecks } from './CloseRunBottlenecks'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import { TOOLS } from '../tools-data'
import { motion, AnimatePresence } from 'framer-motion'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function currentMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

interface SignOff { email: string; signed_at: string }
interface CloseTask {
  task_key: string; label: string
  status: 'pending' | 'complete' | 'blocked'
  completed_at: string | null; completed_by: string | null; notes: string | null
}
interface CloseRun {
  id: string; period: string; status: 'open' | 'in_progress' | 'closed'
  tasks: CloseTask[]; sign_offs: SignOff[]
  created_at: string; closed_at: string | null; closed_by_email: string | null
}

const RUN_STATUS_BADGE: Record<string, string> = {
  open:        'bg-[rgba(245,166,35,0.08)] text-[#f5a623] border border-[rgba(245,166,35,0.2)]',
  in_progress: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]',
  closed:      'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]',
}

const AUTONOMY_BADGE: Record<string, { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
}

const AUTONOMY_DESC: Record<string, string> = {
  auto:    'Executes automatically — no approval required before acting.',
  approve: 'Every decision is routed to you for review before the agent acts.',
}

const HOW_IT_WORKS = [
  { step: '01', label: 'Open',     desc: 'Select a period and click "Open Close Run". Clendan opens the checklist and queues an immediate evaluation.' },
  { step: '02', label: 'Evaluate', desc: 'Auto-checks run against transaction categorisation, reconciliation status, and pending approvals — no manual input needed.' },
  { step: '03', label: 'Confirm',  desc: 'Payroll must be manually confirmed by your team. Mark each manual gate complete before sign-offs can proceed.' },
  { step: '04', label: 'Close',    desc: 'Once all tasks pass, required approvers click Sign Off. Clendan locks the period and writes the full audit record.' },
]

const MONTH_END_CLOSE_CAPABILITIES = TOOLS.find(t => t.slug === 'month-end-close')?.capabilities ?? []

type Tab = 'overview' | 'close-books' | 'executions' | 'approvals' | 'audit'
const TABS: { key: Tab; label: string }[] = [
  { key: 'overview',    label: 'Overview' },
  { key: 'close-books', label: 'Close Books' },
  { key: 'executions',  label: 'Executions' },
  { key: 'approvals',   label: 'Approvals' },
  { key: 'audit',       label: 'Audit' },
]

const EASE = [0.25, 0.46, 0.45, 0.94] as const
const pageVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const sectionVariants = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: EASE } } }
const capabilityVariants = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
const capItemVariants = { hidden: { opacity: 0, x: -8 }, show: { opacity: 1, x: 0, transition: { duration: 0.25, ease: EASE } } }

export function MonthEndCloseClient() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [deployed, setDeployed] = useState<Tool | null>(null)
  const [showConfig, setShowConfig] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deploying, setDeploying] = useState(false)

  const [period, setPeriod] = useState(currentMonth)
  const [run, setRun] = useState<CloseRun | null>(null)
  const [loading, setLoading] = useState(false)
  const [opening, setOpening] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [completingTask, setCompletingTask] = useState<string | null>(null)
  const [signingOff, setSigningOff] = useState(false)

  const fetchDeployed = useCallback(async () => {
    const token = await getToken()
    const res = await fetch(`${API}/tools`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return null
    const json = await res.json()
    const tools: Tool[] = json.data?.tools ?? json.data ?? []
    const found = tools.find((w) => w.type === 'month_end_close') ?? null
    setDeployed(found)
    return found
  }, [getToken])

  const fetchRun = useCallback(async (p: string) => {
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/close-runs`, { headers: { Authorization: `Bearer ${token}` } })
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

  useEffect(() => { fetchDeployed() }, [fetchDeployed])
  useEffect(() => { fetchRun(period) }, [period, fetchRun])

  async function handleOpen() {
    if (!deployed?.id) { toast('Deploy this tool to open a close run', 'error'); return }
    setOpening(true); setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/close-runs`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period }),
      })
      const json = await res.json()
      if (!res.ok) { setError(json.detail ?? 'Failed to open run'); toast(json.detail ?? 'Failed to open run', 'error'); return }
      toast('Month-end close opened', 'success')
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
      const res = await fetch(`${API}/close-runs/${run.id}/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { toast('Refresh failed — please try again', 'error'); return }
      setTimeout(() => fetchRun(period), 2000)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleCompleteTask(taskKey: string) {
    if (!run) return
    setCompletingTask(taskKey)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/close-runs/${run.id}/task/${taskKey}/complete`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const j = await res.json().catch(() => null)
      if (res.ok) { setRun(j.data); toast('Task marked complete', 'success') }
      else { toast(j?.detail ?? `Failed to update task (${res.status})`, 'error') }
    } finally {
      setCompletingTask(null)
    }
  }

  const AUTO_TASKS = new Set(['all_transactions_categorised', 'reconciliation_complete', 'approvals_resolved'])
  const autoTasksResolved = run?.tasks.filter(t => AUTO_TASKS.has(t.task_key)).every(t => t.status === 'complete') ?? false

  async function handleSignOff() {
    if (!run) return
    if (!autoTasksResolved) {
      toast('Resolve all auto-checked tasks before signing off — click Refresh to re-evaluate', 'error')
      return
    }
    setSigningOff(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/close-runs/${run.id}/sign-off`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const j = await res.json()
      if (res.ok) { setRun(j.data); toast('Month-end close signed off', 'success') }
      else { toast(j.detail ?? 'Failed to sign off', 'error') }
    } catch {
      toast('Failed to sign off', 'error')
    } finally {
      setSigningOff(false)
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
      await fetchDeployed()
    } finally {
      setToggling(false)
    }
  }

  async function handleDeploy() {
    setDeploying(true)
    try {
      const token = await getToken()
      if (deployed) {
        await fetch(`${API}/tools/${deployed.id}/pause`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        })
      } else {
        const { getDefaultConfig } = await import('@/components/dashboard/tools/ToolConfigFields')
        await fetch(`${API}/tools`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'month_end_close', autonomy_level: 'auto', config: getDefaultConfig('month_end_close') }),
        })
      }
      await fetchDeployed()
    } finally {
      setDeploying(false)
    }
  }

  const isActive = deployed?.status === 'active'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.approve) : null
  const actionLoading = toggling || deploying

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="px-6 pt-6 pb-24 space-y-6">
      <motion.div variants={sectionVariants}>
        <Link href="/tools" className="text-[12px] font-body text-brand-muted hover:text-brand-secondary transition-colors">
          &larr; Tools
        </Link>
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-heading font-bold text-2xl text-brand-text">Month-End Close</h1>
            {badge && <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>}
          </div>
          <p className="text-xs font-body text-brand-muted max-w-xl">
            Structured close-the-books orchestrator. Auto-evaluates data readiness, enforces payroll
            confirmation, and collects team sign-offs before marking a period closed.
          </p>
        </div>
        {canConfigure && (
          <div className="flex items-center gap-2">
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
          </div>
        )}
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-center gap-2">
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
      </motion.div>

      <motion.div variants={sectionVariants} className="flex gap-1 border-b border-brand-border">
        {TABS.map(t => (
          <button key={t.key} type="button" onClick={() => setActiveTab(t.key)}
            className={`text-xs font-body px-4 py-2.5 border-b-2 transition-colors -mb-px ${
              activeTab === t.key
                ? 'border-[#00C853] text-brand-text'
                : 'border-transparent text-brand-muted hover:text-brand-secondary'
            }`}>
            {t.label}
          </button>
        ))}
      </motion.div>

      <AnimatePresence mode="wait">
        <motion.div key={activeTab}
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}>

          {activeTab === 'overview' && (
            <div className="space-y-4">
              <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-brand-border">
                  <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">How it works</p>
                  <p className="text-[11px] font-body text-brand-muted mt-0.5">Every close run follows this fixed flow — no step can be skipped</p>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-brand-border">
                  {HOW_IT_WORKS.map(({ step, label, desc }) => (
                    <div key={step} className="px-4 py-4 space-y-1.5">
                      <p className="text-[11px] font-body text-brand-muted">{step}</p>
                      <p className="text-xs font-body font-medium text-brand-text">{label}</p>
                      <p className="text-[11px] font-body text-brand-muted leading-relaxed">{desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {deployed && (
                <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Configuration</p>
                  </div>
                  <div className="px-4 py-4 grid grid-cols-2 gap-6">
                    <div className="space-y-1.5">
                      <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Autonomy</p>
                      {badge && <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm inline-block ${badge.className}`}>{badge.label}</span>}
                      <p className="text-[11px] font-body text-brand-muted leading-relaxed">{AUTONOMY_DESC[deployed.autonomy_level] ?? ''}</p>
                    </div>
                    <div className="space-y-1.5">
                      <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Status</p>
                      <p className="text-xs font-body text-brand-text">{deployed.status === 'active' ? 'Running' : 'Paused'}</p>
                      <p className="text-[11px] font-body text-brand-muted">{deployed.status === 'active' ? 'Agent is live and processing' : 'Agent is paused — no runs will fire'}</p>
                    </div>
                  </div>
                </div>
              )}

              <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-brand-border">
                  <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Capabilities</p>
                  <p className="text-[11px] font-body text-brand-muted mt-0.5">What this agent does once deployed and connected to your data</p>
                </div>
                <motion.ul variants={capabilityVariants} initial="hidden" animate="show" className="divide-y divide-brand-border">
                  {MONTH_END_CLOSE_CAPABILITIES.map(cap => (
                    <motion.li key={cap} variants={capItemVariants} className="flex items-start gap-3 px-4 py-3">
                      <span className="text-brand-muted font-body text-[11px] mt-0.5 shrink-0">→</span>
                      <span className="text-xs font-body text-brand-secondary">{cap}</span>
                    </motion.li>
                  ))}
                </motion.ul>
              </div>
            </div>
          )}

          {activeTab === 'close-books' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Period</label>
                  <input
                    type="month"
                    value={period}
                    onChange={e => setPeriod(e.target.value)}
                    className="bg-brand-bg border border-brand-border text-brand-text text-xs font-body rounded-sm px-3 py-1.5 focus:outline-none focus:border-[#00C853]"
                  />
                </div>
                {!loading && !run && (
                  <button type="button" onClick={handleOpen} disabled={opening}
                    className="mt-5 bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] text-xs font-body rounded-sm px-4 py-1.5 transition-all disabled:opacity-50">
                    {opening ? 'Opening…' : 'Open Close Run'}
                  </button>
                )}
                {run && (
                  <button type="button" onClick={handleRefresh}
                    disabled={refreshing || run.status === 'closed'}
                    className="mt-5 text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors disabled:opacity-50">
                    {refreshing ? 'Refreshing…' : 'Refresh'}
                  </button>
                )}
              </div>

              {error && <p className="text-xs font-body text-[#ff4d6d]">{error}</p>}

              {loading && (
                <div className="space-y-3">
                  {[1, 2, 3].map(i => <div key={i} className="h-12 animate-pulse bg-brand-elevated rounded-sm" />)}
                </div>
              )}

              {!loading && !run && !error && (
                <div className="bg-brand-surface border border-brand-border rounded-sm p-6 text-center space-y-1">
                  <p className="text-xs font-body text-brand-text">No close run for {period}</p>
                  <p className="text-[12px] font-body text-brand-muted">
                    Opening a close run starts the checklist for this period. Clendan will automatically
                    evaluate data readiness — you only need to manually confirm payroll and sign-offs.
                  </p>
                </div>
              )}

              <AnimatePresence mode="wait">
                {!loading && run && (
                  <motion.div key={run.id}
                    initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2, ease: 'easeOut' }}
                    className="space-y-4">
                    <div className="flex items-center gap-2">
                      <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm ${RUN_STATUS_BADGE[run.status] ?? ''}`}>
                        {run.status.replace('_', ' ').toUpperCase()}
                      </span>
                      <span className="text-[11px] font-body text-brand-muted">Period {run.period}</span>
                    </div>

                    <CloseRunChecklist
                      tasks={run.tasks}
                      onCompleteTask={handleCompleteTask}
                      completingTask={completingTask}
                      runClosed={run.status === 'closed'}
                    />

                    <CloseRunSignOffs
                      signOffs={run.sign_offs}
                      onSignOff={handleSignOff}
                      signingOff={signingOff}
                      autoTasksResolved={autoTasksResolved}
                      runClosed={run.status === 'closed'}
                    />

                    <CloseRunBottlenecks runId={run.id} tasks={run.tasks} />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {activeTab === 'executions' && <ToolExecutionsTab toolId={deployed?.id ?? null} />}
          {activeTab === 'approvals' && <ToolApprovalsTab toolId={deployed?.id ?? null} />}
          {activeTab === 'audit' && <ToolAuditTab toolId={deployed?.id ?? null} />}
        </motion.div>
      </AnimatePresence>

      {showConfig && (
        <ConfigDrawer
          tool={deployed}
          toolType="month_end_close"
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); fetchDeployed() }}
        />
      )}
    </motion.div>
  )
}

interface SignOffsProps {
  signOffs: SignOff[]
  onSignOff: () => void
  signingOff: boolean
  autoTasksResolved: boolean
  runClosed: boolean
}

function CloseRunSignOffs({ signOffs, onSignOff, signingOff, autoTasksResolved, runClosed }: SignOffsProps) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-brand-border flex items-center justify-between">
        <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Sign-offs</p>
        {!runClosed && (
          <button type="button" onClick={onSignOff}
            disabled={signingOff || !autoTasksResolved}
            title={!autoTasksResolved ? 'All auto-checked tasks must pass before signing off' : undefined}
            className="text-[11px] font-body bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1 transition-all disabled:opacity-40 disabled:cursor-not-allowed">
            {signingOff ? 'Signing off…' : 'Sign Off'}
          </button>
        )}
      </div>
      <p className="px-4 py-2 text-[11px] font-body text-brand-muted border-b border-brand-border">
        A sign-off is your confirmation that you have reviewed this period&apos;s financials and
        they are accurate. Each team member who needs to approve should click &quot;Sign Off&quot; individually.
      </p>
      {signOffs.length === 0 ? (
        <p className="px-4 py-4 text-xs font-body text-brand-muted">No sign-offs yet.</p>
      ) : (
        <div className="divide-y divide-brand-border">
          {signOffs.map(s => (
            <div key={s.email} className="px-4 py-2.5 flex items-center justify-between">
              <span className="text-xs font-body text-brand-text">{s.email}</span>
              <span className="text-[11px] font-body text-brand-muted">
                {new Date(s.signed_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
