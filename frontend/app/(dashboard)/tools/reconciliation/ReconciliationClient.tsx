'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { useCurrency, useToast } from '@/components/Providers'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import { ReconciliationRun, ReconciliationItem } from './types'
import { RunControls } from './RunControls'
import { RunHistory } from './RunHistory'
import { ReconciliationTable } from './ReconciliationTable'
import { ToolExecutionsTab } from '@/components/dashboard/tools/ToolExecutionsTab'
import { ToolApprovalsTab } from '@/components/dashboard/tools/ToolApprovalsTab'
import { ToolAuditTab } from '@/components/dashboard/tools/ToolAuditTab'
import { TOOLS } from '../tools-data'
import { motion, AnimatePresence } from 'framer-motion'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Tab = 'overview' | 'executions' | 'approvals' | 'audit'
const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'executions', label: 'Executions' },
  { key: 'approvals', label: 'Approvals' },
  { key: 'audit', label: 'Audit' },
]

function defaultPeriodStart() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10)
}
function defaultPeriodEnd() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().slice(0, 10)
}

interface OverviewProps {
  periodStart: string
  periodEnd: string
  toolId: string | null
  running: boolean
  runs: ReconciliationRun[]
  runsLoading: boolean
  selectedId: string | null
  onPeriodStartChange: (v: string) => void
  onPeriodEndChange: (v: string) => void
  onRun: () => void
  onSelectRun: (run: ReconciliationRun) => void
}

function OverviewTab({
  periodStart, periodEnd, toolId, running,
  runs, runsLoading, selectedId,
  onPeriodStartChange, onPeriodEndChange, onRun, onSelectRun,
}: OverviewProps) {
  return (
    <>
      <RunControls
        periodStart={periodStart}
        periodEnd={periodEnd}
        toolReady={!!toolId}
        running={running}
        onPeriodStartChange={onPeriodStartChange}
        onPeriodEndChange={onPeriodEndChange}
        onRun={onRun}
      />
      <div className="space-y-2 mt-5">
        <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Run History</p>
        <RunHistory runs={runs} loading={runsLoading} selectedId={selectedId} onSelect={onSelectRun} />
      </div>
    </>
  )
}

const RECONCILIATION_CAPABILITIES = TOOLS.find(t => t.slug === 'reconciliation')?.capabilities ?? []


const pageVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
const EASE = [0.25, 0.46, 0.45, 0.94] as const
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: EASE } },
}
const capabilityVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
}
const capItemVariants = {
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { duration: 0.25, ease: EASE } },
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
  { step: '01', label: 'Trigger',       desc: 'Tool activates on a schedule or incoming event. Data is pulled from connected integrations.' },
  { step: '02', label: 'Execute',       desc: 'Agent processes the data using your configured rules and AI reasoning.' },
  { step: '03', label: 'Policy check',  desc: 'Every output is validated by the policy engine before any action is taken. Cannot be skipped.' },
  { step: '04', label: 'Audit',         desc: 'Full decision and reasoning trace written to the immutable audit log before returning.' },
]

export function ReconciliationClient() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const { currency } = useCurrency()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [runs, setRuns] = useState<ReconciliationRun[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [selectedRun, setSelectedRun] = useState<ReconciliationRun | null>(null)
  const [items, setItems] = useState<ReconciliationItem[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)
  const [periodStart, setPeriodStart] = useState(defaultPeriodStart)
  const [periodEnd, setPeriodEnd] = useState(defaultPeriodEnd)
  const [deployed, setDeployed] = useState<Tool | null>(null)
  const [running, setRunning] = useState(false)
  const [showConfig, setShowConfig] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [polling, setPolling] = useState(false)
  const pollRunCountRef = useRef(0)

  const fetchDeployed = useCallback(async () => {
    const token = await getToken()
    const res = await fetch(`${API}/v1/tools`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return
    const json = await res.json()
    const tools: Tool[] = json.data?.tools ?? json.data ?? []
    setDeployed(tools.find((w) => w.type === 'reconciliation') ?? null)
  }, [getToken])

  const fetchRuns = useCallback(async () => {
    const token = await getToken()
    const res = await fetch(`${API}/v1/reconciliation/runs?limit=20`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return
    const json = await res.json()
    const list: ReconciliationRun[] = json.data?.runs ?? []
    setRuns(list)
    return list
  }, [getToken])

  const fetchItems = useCallback(async (runId: string) => {
    setItemsLoading(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/reconciliation/runs/${runId}/items`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const json = await res.json()
        setItems(json.data?.items ?? [])
      }
    } finally {
      setItemsLoading(false)
    }
  }, [getToken])

  useEffect(() => {
    if (!polling) return
    let active = true
    const interval = setInterval(async () => {
      if (!active) return
      const list = await fetchRuns()
      if (list && list.length > pollRunCountRef.current) {
        active = false
        setPolling(false)
        setRunning(false)
      }
    }, 2000)
    const timeout = setTimeout(() => {
      active = false
      setPolling(false)
      setRunning(false)
    }, 5 * 60 * 1000)
    return () => {
      active = false
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, [polling, fetchRuns])

  useEffect(() => {
    async function init() {
      const token = await getToken()
      const toolsRes = await fetch(`${API}/v1/tools`, { headers: { Authorization: `Bearer ${token}` } })
      if (toolsRes.ok) {
        const toolsJson = await toolsRes.json()
        const tools: Tool[] = toolsJson.data?.tools ?? toolsJson.data ?? []
        const deployedTool = tools.find((w) => w.type === 'reconciliation') ?? null
        if (deployedTool) setDeployed(deployedTool)
      }
      setRunsLoading(true)
      const list = await fetchRuns()
      setRunsLoading(false)
      if (list?.[0]) { setSelectedRun(list[0]); fetchItems(list[0].id) }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleToggle() {
    if (!deployed) return
    setToggling(true)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/tools/${deployed.id}/pause`, {
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
        await fetch(`${API}/v1/tools/${deployed.id}/pause`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        })
      } else {
        const { getDefaultConfig } = await import('@/components/dashboard/tools/ToolConfigFields')
        await fetch(`${API}/v1/tools`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'reconciliation', autonomy_level: 'approve', config: getDefaultConfig('reconciliation') }),
        })
      }
      await fetchDeployed()
    } finally {
      setDeploying(false)
    }
  }

  async function handleRun() {
    if (!deployed?.id || running) return
    setRunning(true)
    try {
      const token = await getToken()
      const cfg = (deployed.config_json as Record<string, unknown> | null)
      const configAccountIds = cfg?.account_ids
      const runAccountIds = Array.isArray(configAccountIds) && configAccountIds.length > 0 ? configAccountIds as string[] : null
      const configIntegrationSources = cfg?.integration_sources
      const runIntegrationSources = Array.isArray(configIntegrationSources) && configIntegrationSources.length > 0 ? configIntegrationSources as string[] : null
      const res = await fetch(`${API}/v1/reconciliation/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_start: periodStart, period_end: periodEnd, tool_id: deployed.id, account_ids: runAccountIds, integration_sources: runIntegrationSources }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => null)
        toast(json?.detail ?? `Run failed (${res.status})`, 'error')
        setRunning(false)
        return
      }
      pollRunCountRef.current = runs.length
      setPolling(true)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Network error', 'error')
      setRunning(false)
    }
  }

  async function handleExport(runId: string) {
    const token = await getToken()
    const params = new URLSearchParams()
    if (currency && currency !== 'GBP') params.set('display_currency', currency)
    const res = await fetch(`${API}/v1/reconciliation/runs/${runId}/export?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) { toast('Export failed — please try again', 'error'); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `reconciliation_${runId}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const isActive = deployed?.status === 'active'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.approve) : null
  const actionLoading = toggling || deploying

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-6">
      <motion.div variants={sectionVariants}>
        <Link href="/tools" className="text-[11px] font-mono text-brand-muted hover:text-brand-secondary transition-colors">
          ← Tools
        </Link>
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-heading font-bold text-2xl text-brand-text">Reconciliation</h1>
            {badge && <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>}
          </div>
          <p className="text-xs font-mono text-brand-muted">
            Match bank transactions against invoices. Detects unmatched items and flags anomalies.
          </p>
        </div>
        {canConfigure && (
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setShowConfig(true)}
              className="text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors">
              Configure
            </button>
            <button type="button" onClick={isActive ? handleToggle : handleDeploy} disabled={actionLoading}
              className={`text-xs font-mono rounded-sm px-3 py-1.5 transition-all disabled:opacity-50 ${
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
            <span className="text-xs font-mono text-[#00C853]">Active</span>
          </>
        ) : (
          <>
            <span className="h-2 w-2 rounded-full bg-brand-muted" />
            <span className="text-xs font-mono text-brand-muted">{deployed ? 'Paused' : 'Not deployed'}</span>
          </>
        )}
      </motion.div>

      <motion.div variants={sectionVariants} className="flex gap-1 border-b border-brand-border">
        {TABS.map(t => (
          <button key={t.key} type="button" onClick={() => setActiveTab(t.key)}
            className={`text-xs font-mono px-4 py-2.5 border-b-2 transition-colors -mb-px ${
              activeTab === t.key
                ? 'border-[#00C853] text-brand-text'
                : 'border-transparent text-brand-muted hover:text-brand-secondary'
            }`}>
            {t.label}
          </button>
        ))}
      </motion.div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          {activeTab === 'overview' && (
            <div className="space-y-4">
              <OverviewTab
                periodStart={periodStart} periodEnd={periodEnd}
                toolId={deployed?.id ?? null} running={running}
                runs={runs} runsLoading={runsLoading} selectedId={selectedRun?.id ?? null}
                onPeriodStartChange={setPeriodStart} onPeriodEndChange={setPeriodEnd}
                onRun={handleRun}
                onSelectRun={(r) => { setSelectedRun(r); fetchItems(r.id); setModalOpen(true) }}
              />

              {/* How it works */}
              <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-brand-border">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">How it works</p>
                  <p className="text-[10px] font-mono text-brand-muted mt-0.5">Every run follows this fixed execution flow — no step can be skipped</p>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-brand-border">
                  {HOW_IT_WORKS.map(({ step, label, desc }) => (
                    <div key={step} className="px-4 py-4 space-y-1.5">
                      <p className="text-[10px] font-mono text-brand-muted">{step}</p>
                      <p className="text-xs font-mono font-medium text-brand-text">{label}</p>
                      <p className="text-[10px] font-mono text-brand-muted leading-relaxed">{desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Configuration */}
              {deployed && (
                <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Configuration</p>
                  </div>
                  <div className="px-4 py-4 grid grid-cols-3 gap-6">
                    <div className="space-y-1.5">
                      <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Autonomy</p>
                      {badge && <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm inline-block ${badge.className}`}>{badge.label}</span>}
                      <p className="text-[10px] font-mono text-brand-muted leading-relaxed">{AUTONOMY_DESC[deployed.autonomy_level] ?? ''}</p>
                    </div>
                    <div className="space-y-1.5">
                      <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Version</p>
                      <p className="text-xs font-mono text-brand-text">v{deployed.version}</p>
                      <p className="text-[10px] font-mono text-brand-muted">Increments on every config change</p>
                    </div>
                    <div className="space-y-1.5">
                      <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Status</p>
                      <p className="text-xs font-mono text-brand-text">{deployed.status === 'active' ? 'Running' : 'Paused'}</p>
                      <p className="text-[10px] font-mono text-brand-muted">{deployed.status === 'active' ? 'Agent is live and processing' : 'Agent is paused — no runs will fire'}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Capabilities */}
              <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-brand-border">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Capabilities</p>
                  <p className="text-[10px] font-mono text-brand-muted mt-0.5">What this agent does once deployed and connected to your data</p>
                </div>
                <motion.ul variants={capabilityVariants} initial="hidden" animate="show" className="divide-y divide-brand-border">
                  {RECONCILIATION_CAPABILITIES.map(cap => (
                    <motion.li key={cap} variants={capItemVariants} className="flex items-start gap-3 px-4 py-3">
                      <span className="text-brand-muted font-mono text-[10px] mt-0.5 shrink-0">→</span>
                      <span className="text-xs font-mono text-brand-secondary">{cap}</span>
                    </motion.li>
                  ))}
                </motion.ul>
              </div>
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
          toolType="reconciliation"
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); fetchDeployed() }}
        />
      )}

      <AnimatePresence>
        {modalOpen && selectedRun && (
          <motion.div
            key="run-modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[rgba(0,0,0,0.7)] p-8"
            onClick={() => setModalOpen(false)}
          >
            <motion.div
              key="run-modal-panel"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="relative bg-brand-surface border border-brand-border rounded-sm w-full max-w-6xl"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-brand-border">
                <div className="flex items-center gap-3">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
                    Results · {new Date(selectedRun.period_start).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })} – {new Date(selectedRun.period_end).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </p>
                  {selectedRun.triggered_by_email && (
                    <p className="text-[10px] font-mono text-brand-muted">
                      by {selectedRun.triggered_by_email}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="text-brand-muted hover:text-brand-text transition-colors"
                >
                  <span className="text-lg leading-none">✕</span>
                </button>
              </div>
              <ReconciliationTable items={items} loading={itemsLoading} runId={selectedRun.id} onExport={handleExport} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
