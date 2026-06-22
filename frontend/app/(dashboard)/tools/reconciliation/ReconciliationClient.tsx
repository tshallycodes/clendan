'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
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

interface BankAccount {
  id: string
  name: string
  subtype: string
  source: string
}

interface OverviewProps {
  periodStart: string
  periodEnd: string
  accountId: string
  accounts: BankAccount[]
  toolId: string | null
  running: boolean
  runs: ReconciliationRun[]
  runsLoading: boolean
  selectedRun: ReconciliationRun | null
  items: ReconciliationItem[]
  itemsLoading: boolean
  onPeriodStartChange: (v: string) => void
  onPeriodEndChange: (v: string) => void
  onAccountChange: (v: string) => void
  onRun: () => void
  onSelectRun: (run: ReconciliationRun) => void
  onExport: (runId: string) => void
}

function OverviewTab({
  periodStart, periodEnd, accountId, accounts, toolId, running,
  runs, runsLoading, selectedRun, items, itemsLoading,
  onPeriodStartChange, onPeriodEndChange, onAccountChange, onRun, onSelectRun, onExport,
}: OverviewProps) {
  return (
    <>
      <RunControls
        periodStart={periodStart}
        periodEnd={periodEnd}
        accountId={accountId}
        accounts={accounts}
        toolReady={!!toolId}
        running={running}
        onPeriodStartChange={onPeriodStartChange}
        onPeriodEndChange={onPeriodEndChange}
        onAccountChange={onAccountChange}
        onRun={onRun}
      />
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-5">
        <div className="space-y-2">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Run History</p>
          <RunHistory runs={runs} loading={runsLoading} selectedId={selectedRun?.id ?? null} onSelect={onSelectRun} />
        </div>
        <div className="space-y-2">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">
            {selectedRun
              ? `Results · ${new Date(selectedRun.period_start).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} – ${new Date(selectedRun.period_end).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}`
              : 'Results'}
          </p>
          {selectedRun ? (
            <ReconciliationTable items={items} loading={itemsLoading} runId={selectedRun.id} onExport={onExport} />
          ) : (
            !runsLoading && (
              <div className="bg-brand-surface border border-brand-border rounded-sm p-8 text-center">
                <p className="text-xs font-mono text-brand-muted">Select a run to view results.</p>
              </div>
            )
          )}
        </div>
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
  suggest: { label: 'Suggest', className: 'bg-brand-surface text-brand-muted border border-brand-border' },
}

export function ReconciliationClient() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [runs, setRuns] = useState<ReconciliationRun[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [selectedRun, setSelectedRun] = useState<ReconciliationRun | null>(null)
  const [items, setItems] = useState<ReconciliationItem[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)
  const [periodStart, setPeriodStart] = useState(defaultPeriodStart)
  const [periodEnd, setPeriodEnd] = useState(defaultPeriodEnd)
  const [accountId, setAccountId] = useState('')
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [deployed, setDeployed] = useState<Tool | null>(null)
  const [running, setRunning] = useState(false)
  const [showConfig, setShowConfig] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deploying, setDeploying] = useState(false)

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
    async function init() {
      const token = await getToken()
      const [toolsRes, accountsRes] = await Promise.all([
        fetch(`${API}/v1/tools`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/v1/reconciliation/accounts`, { headers: { Authorization: `Bearer ${token}` } }),
      ])
      if (toolsRes.ok) {
        const toolsJson = await toolsRes.json()
        const tools: Tool[] = toolsJson.data?.tools ?? toolsJson.data ?? []
        const rec = tools.find((w) => w.type === 'reconciliation')
        if (rec) setDeployed(rec)
      }
      if (accountsRes.ok) {
        const accountsJson = await accountsRes.json()
        setAccounts(accountsJson.data?.accounts ?? [])
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
      const configAccountIds = (deployed.config_json as Record<string, unknown> | null)?.account_ids
      const runAccountIds = accountId
        ? [accountId]
        : (Array.isArray(configAccountIds) && configAccountIds.length > 0 ? configAccountIds as string[] : null)
      const res = await fetch(`${API}/v1/reconciliation/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_start: periodStart, period_end: periodEnd, tool_id: deployed.id, account_ids: runAccountIds }),
      })
      if (!res.ok) return
      const json = await res.json()
      const newRun: ReconciliationRun = json.data
      const updated = await fetchRuns()
      const fresh = updated?.find((r) => r.id === newRun.id) ?? newRun
      setSelectedRun(fresh)
      fetchItems(fresh.id)
    } finally {
      setRunning(false)
    }
  }

  async function handleExport(runId: string) {
    const token = await getToken()
    const res = await fetch(`${API}/v1/reconciliation/runs/${runId}/export`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `reconciliation_${runId}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const isActive = deployed?.status === 'active'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.suggest) : null
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
            {deployed && <span className="text-[10px] font-mono text-brand-muted">v{deployed.version}</span>}
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
            <>
              <OverviewTab
                periodStart={periodStart} periodEnd={periodEnd} accountId={accountId} accounts={accounts}
                toolId={deployed?.id ?? null} running={running}
                runs={runs} runsLoading={runsLoading} selectedRun={selectedRun}
                items={items} itemsLoading={itemsLoading}
                onPeriodStartChange={setPeriodStart} onPeriodEndChange={setPeriodEnd}
                onAccountChange={setAccountId}
                onRun={handleRun} onSelectRun={(r) => { setSelectedRun(r); fetchItems(r.id) }}
                onExport={handleExport}
              />
              <motion.ul
                variants={capabilityVariants}
                initial="hidden"
                animate="show"
                className="bg-brand-surface border border-brand-border rounded-sm divide-y divide-brand-border mt-5"
              >
                {RECONCILIATION_CAPABILITIES.map(cap => (
                  <motion.li key={cap} variants={capItemVariants} className="flex items-start gap-3 px-4 py-3">
                    <span className="text-brand-muted font-mono text-[10px] mt-0.5 shrink-0">→</span>
                    <span className="text-xs font-mono text-brand-secondary">{cap}</span>
                  </motion.li>
                ))}
              </motion.ul>
            </>
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
    </motion.div>
  )
}
