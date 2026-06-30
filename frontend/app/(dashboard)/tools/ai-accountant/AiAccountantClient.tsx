'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { useToast } from '@/components/Providers'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import { ToolExecutionsTab } from '@/components/dashboard/tools/ToolExecutionsTab'
import { ToolApprovalsTab } from '@/components/dashboard/tools/ToolApprovalsTab'
import { ToolAuditTab } from '@/components/dashboard/tools/ToolAuditTab'
import { TransactionsTab, type StatusFilter } from './TransactionsTab'
import { MonthEndCloseTab } from './MonthEndCloseTab'
import { PayrollRecTab } from './PayrollRecTab'
import { JournalEntriesTab } from './JournalEntriesTab'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import type { Transaction } from '@/components/dashboard/transactions/TransactionRow'
import { motion, AnimatePresence } from 'framer-motion'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const PAGE_SIZE = 50

type Tab = 'overview' | 'transactions' | 'executions' | 'approvals' | 'audit' | 'month-end-close' | 'payroll' | 'journal-entries'
const TABS: { key: Tab; label: string }[] = [
  { key: 'overview',        label: 'Overview' },
  { key: 'executions',      label: 'Executions' },
  { key: 'approvals',       label: 'Approvals' },
  { key: 'audit',           label: 'Audit' },
  { key: 'transactions',    label: 'Transactions' },
  { key: 'month-end-close', label: 'Month-End Close' },
  { key: 'payroll',         label: 'Payroll Rec' },
  { key: 'journal-entries', label: 'Journal Entries' },
]

const HOW_IT_WORKS = [
  { step: '01', label: 'Ingest',       desc: 'Every new bank transaction is pulled from connected accounts and queued for classification.' },
  { step: '02', label: 'Classify',     desc: 'Claude assigns a chart-of-accounts category with a confidence score. Low-confidence items are flagged for review.' },
  { step: '03', label: 'Policy check', desc: 'Policy engine validates the classification before any write. Blocked items are never committed without human sign-off.' },
  { step: '04', label: 'Audit',        desc: 'Every categorisation decision — including reasoning and confidence — is written to the immutable audit log.' },
]

const CAPABILITIES = [
  'Automatic transaction categorisation with confidence scoring',
  'Human review queue for low-confidence categorisations',
  'Learns from your team\'s manual corrections — configurable example window',
  'Strict chart-of-accounts enforcement — only codes that exist in your COA',
  'Month-end close orchestration — auto-triggered on your configured day each month',
  'Payroll reconciliation with keyword-matched transaction detection and ghost employee flagging',
  'Payroll journal entry posting with automated approval routing',
  'Batch processing for high-volume transaction periods',
]

const AUTONOMY_BADGE: Record<string, { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
}
const AUTONOMY_DESC: Record<string, string> = {
  auto:    'Executes automatically — no approval required before acting.',
  approve: 'Every decision is routed to you for review before the agent acts.',
}

const EASE = [0.25, 0.46, 0.45, 0.94] as const
const pageVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: EASE } },
}
const capabilityVariants = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
const capItemVariants = {
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { duration: 0.25, ease: EASE } },
}

export function AiAccountantClient() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [deployed, setDeployed] = useState<Tool | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [listTotal, setListTotal] = useState(0)
  const [pendingCount, setPendingCount] = useState(0)
  const [categorisedCount, setCategorisedCount] = useState(0)
  const [matchedCount, setMatchedCount] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [categories, setCategories] = useState<{ income: string[]; expenses: string[] }>({ income: [], expenses: [] })
  const [filter, setFilter] = useState<StatusFilter>('all')
  const filterRef = useRef<StatusFilter>('all')
  const filterMountedRef = useRef(false)
  const [running, setRunning] = useState(false)
  const [polling, setPolling] = useState(false)
  const [showConfig, setShowConfig] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [pendingApprovalCount, setPendingApprovalCount] = useState(0)
  const pollStartCategorisedRef = useRef(0)
  const triggeredExecutionIdRef = useRef<string | null>(null)

  const fetchDeployed = useCallback(async () => {
    const token = await getToken()
    const res = await fetch(`${API}/tools`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return null
    const json = await res.json()
    const tools: Tool[] = json.data?.tools ?? json.data ?? []
    const found = tools.find((w) => w.type === 'ai_accountant') ?? null
    setDeployed(found)
    return found
  }, [getToken])

  const fetchTransactions = useCallback(async (fromOffset = 0, replace = true, statusFilter?: StatusFilter) => {
    const token = await getToken()
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(fromOffset) })
    const sf = statusFilter ?? filterRef.current
    if (sf && sf !== 'all') params.set('status', sf)
    const res = await fetch(`${API}/transactions?${params}`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return
    const json = await res.json()
    const txns: Transaction[] = json.data?.transactions ?? []
    const serverPending: number = json.data?.pending_count ?? 0
    const serverCategorised: number = json.data?.categorised_count ?? 0
    const serverMatched: number = json.data?.matched_count ?? 0
    setListTotal(json.data?.total ?? 0)
    setPendingCount(serverPending)
    setCategorisedCount(serverCategorised)
    setMatchedCount(serverMatched)
    if (replace) { setTransactions(txns); setOffset(txns.length) }
    else { setTransactions(prev => [...prev, ...txns]); setOffset(prev => prev + txns.length) }
    return { txns, pending: serverPending, categorised: serverCategorised, matched: serverMatched }
  }, [getToken])

  const fetchCategories = useCallback(async () => {
    const token = await getToken()
    const res = await fetch(`${API}/transactions/categories`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return
    const json = await res.json()
    if (json.data) setCategories(json.data)
  }, [getToken])

  const fetchPendingApprovals = useCallback(async (toolId: string) => {
    const token = await getToken()
    const res = await fetch(`${API}/dashboard/approvals?tool_id=${toolId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return
    const json = await res.json()
    const approvals: { status: string }[] = json.data?.approvals ?? []
    setPendingApprovalCount(approvals.filter(a => a.status === 'pending').length)
  }, [getToken])

  useEffect(() => {
    async function init() {
      const deployedTool = await fetchDeployed()
      await Promise.all([fetchTransactions(), fetchCategories()])
      if (deployedTool?.id) fetchPendingApprovals(deployedTool.id)
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!polling) return
    let active = true

    const checkExecution = async (token: string): Promise<'running' | 'done' | 'blocked' | 'failed'> => {
      const execId = triggeredExecutionIdRef.current
      if (!execId || !deployed?.id) return 'running'
      const res = await fetch(
        `${API}/dashboard/executions?tool_id=${deployed.id}&limit=10`,
        { headers: { Authorization: `Bearer ${token}` } },
      ).catch(() => null)
      if (!res?.ok) return 'running'
      const json = await res.json()
      const exec = (json.data?.executions ?? []).find((e: { id: string }) => e.id === execId)
      if (!exec) return 'running'
      if (exec.status === 'queued' || exec.status === 'running') return 'running'
      if (exec.status === 'failed') return 'failed'
      if (exec.decision === 'blocked') return 'blocked'
      return 'done'
    }

    const interval = setInterval(async () => {
      if (!active) return
      const token = await getToken()
      if (!token) return
      const execState = await checkExecution(token)

      if (execState === 'failed') {
        active = false
        setPolling(false)
        setRunning(false)
        toast('Categorisation failed — check the Executions tab for details', 'error')
        return
      }
      if (execState === 'blocked') {
        active = false
        setPolling(false)
        setRunning(false)
        await fetchTransactions(0, true)
        toast('Categorisation blocked — confidence too low. Lower the confidence threshold in tool config.', 'error')
        return
      }

      const result = await fetchTransactions(0, true)
      if (!result) return
      const newCategorisedCount = result.categorised + result.matched
      if (execState === 'done' || newCategorisedCount > pollStartCategorisedRef.current) {
        active = false
        setPolling(false)
        setRunning(false)
        if (deployed?.id) fetchPendingApprovals(deployed.id)
        toast('Categorisation complete', 'success')
      }
    }, 2000)
    const timeout = setTimeout(() => {
      active = false
      setPolling(false)
      setRunning(false)
    }, 5 * 60 * 1000)
    return () => { active = false; clearInterval(interval); clearTimeout(timeout) }
  }, [polling, fetchTransactions, fetchPendingApprovals, toast, getToken, deployed?.id])

  useEffect(() => {
    filterRef.current = filter
    if (!filterMountedRef.current) { filterMountedRef.current = true; return }
    fetchTransactions(0, true, filter !== 'all' ? filter : undefined)
  }, [filter, fetchTransactions])

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
          body: JSON.stringify({ type: 'ai_accountant', autonomy_level: 'approve', config: getDefaultConfig('ai_accountant') }),
        })
      }
      await fetchDeployed()
    } finally {
      setDeploying(false)
    }
  }

  async function handleCategoriseNow() {
    if (!deployed?.id) { toast('Deploy the tool to continue', 'error'); return }
    if (running) return
    const pending = transactions.filter(t => t.status !== 'categorised' && t.status !== 'matched')
    if (pendingCount === 0 || pending.length === 0) { toast('No uncategorised transactions', 'info'); return }
    setRunning(true)
    pollStartCategorisedRef.current = categorisedCount + matchedCount
    triggeredExecutionIdRef.current = null
    try {
      const token = await getToken()
      const res = await fetch(`${API}/agents/${deployed.id}/trigger`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `ai-accountant-${deployed.id}-${Date.now()}`,
        },
        body: JSON.stringify({ payload: { transaction_ids: pending.map(t => t.id) } }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => null)
        toast(json?.detail ?? `Trigger failed (${res.status})`, 'error')
        setRunning(false)
        return
      }
      const triggerJson = await res.json().catch(() => null)
      triggeredExecutionIdRef.current = triggerJson?.data?.execution_id ?? null
      setPolling(true)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Network error', 'error')
      setRunning(false)
    }
  }

  async function handleExportCsv() {
    const token = await getToken()
    const params = new URLSearchParams()
    if (filter !== 'all') params.set('status', filter)
    const res = await fetch(`${API}/transactions/export?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) { toast('Export failed — please try again', 'error'); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `transactions${filter !== 'all' ? `_${filter}` : ''}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleLoadMore() {
    setLoadingMore(true)
    try { await fetchTransactions(offset, false, filter !== 'all' ? filter : undefined) } finally { setLoadingMore(false) }
  }

  function handleCategoryUpdate(id: string, category: string) {
    setTransactions(prev => prev.map(t => t.id === id ? { ...t, ai_category: category, status: 'categorised' } : t))
  }

  const isActive = deployed?.status === 'active'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.approve) : null
  const actionLoading = toggling || deploying

  const totalAll = pendingCount + categorisedCount + matchedCount
  const categorisedPct = totalAll > 0 ? Math.round(((categorisedCount + matchedCount) / totalAll) * 100) : 0
  const counts: Record<StatusFilter, number> = {
    all: totalAll, pending: pendingCount, categorised: categorisedCount, matched: matchedCount,
  }

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-6">
      <motion.div variants={sectionVariants}>
        <Link href="/tools" className="text-[11px] font-mono text-brand-muted hover:text-brand-secondary transition-colors">
          ← Tools
        </Link>
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-heading font-bold text-2xl text-brand-text">AI Accountant</h1>
            {badge && <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>}
          </div>
          <p className="text-xs font-mono text-brand-muted max-w-xl">
            Automate transaction categorisation, invoice matching, and month-end close with AI.
          </p>
        </div>
        {canConfigure && (
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setShowConfig(true)}
              className="text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-bg rounded-sm px-3 py-1.5 transition-colors">
              Configure
            </button>
            <button type="button" onClick={isActive ? handleToggle : handleDeploy} disabled={actionLoading}
              className={`text-xs font-mono rounded-sm px-3 py-1.5 transition-all disabled:opacity-50 ${
                isActive
                  ? 'border border-brand-border text-brand-text hover:bg-brand-bg'
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
          <button
            key={t.key}
            type="button"
            onClick={() => {
              setActiveTab(t.key)
              if (t.key === 'approvals' && deployed?.id) {
                fetchPendingApprovals(deployed.id)
                setPendingApprovalCount(0)
              }
            }}
            className={`relative text-xs font-mono px-4 py-2.5 border-b-2 transition-colors -mb-px ${
              activeTab === t.key
                ? 'border-[#00C853] text-brand-text'
                : 'border-transparent text-brand-muted hover:text-brand-secondary'
            }`}>
            {t.label}
            {t.key === 'approvals' && pendingApprovalCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-[#00a8cc] text-[9px] font-mono font-semibold text-black leading-none">
                <span className="absolute inset-0 rounded-full bg-[#00a8cc] animate-ping opacity-60" />
                <span className="relative">{pendingApprovalCount > 99 ? '99+' : pendingApprovalCount}</span>
              </span>
            )}
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
              {/* Stats */}
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
                  <p className="text-[10px] font-mono text-brand-muted uppercase tracking-wider">Total</p>
                  <p className="text-2xl font-mono font-semibold text-brand-text mt-1">{totalAll}</p>
                  <p className="text-[10px] font-mono text-brand-muted mt-1">transactions</p>
                </div>
                <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
                  <p className="text-[10px] font-mono text-brand-muted uppercase tracking-wider">Uncategorised</p>
                  <p className={`text-2xl font-mono font-semibold mt-1 ${pendingCount > 0 ? 'text-[#f5a623]' : 'text-brand-text'}`}>
                    {pendingCount}
                  </p>
                  <p className="text-[10px] font-mono text-brand-muted mt-1">not yet categorised</p>
                </div>
                <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
                  <p className="text-[10px] font-mono text-brand-muted uppercase tracking-wider">Categorised</p>
                  <p className={`text-2xl font-mono font-semibold mt-1 ${categorisedPct >= 90 ? 'text-[#00C853]' : 'text-brand-text'}`}>
                    {categorisedPct}%
                  </p>
                  <p className="text-[10px] font-mono text-brand-muted mt-1">{categorisedCount + matchedCount} of {totalAll}</p>
                </div>
                <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
                  <p className="text-[10px] font-mono text-brand-muted uppercase tracking-wider">Matched</p>
                  <p className="text-2xl font-mono font-semibold text-[#00C853] mt-1">{matchedCount}</p>
                  <p className="text-[10px] font-mono text-brand-muted mt-1">to invoices</p>
                </div>
              </div>

              {/* Quick action */}
              {pendingCount > 0 && (
                <div className="bg-brand-surface border border-brand-border rounded-sm p-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-mono text-brand-text">{pendingCount} transaction{pendingCount !== 1 ? 's' : ''} not yet categorised</p>
                    <p className="text-[10px] font-mono text-brand-muted mt-0.5">Run the AI to categorise automatically, or review and categorise manually in the Transactions tab</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => { setActiveTab('transactions'); setFilter('pending') }}
                      className="text-xs font-mono bg-transparent border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-4 py-1.5 transition-colors"
                    >
                      View
                    </button>
                    <button
                      type="button"
                      onClick={handleCategoriseNow}
                      disabled={running}
                      className="text-xs font-mono bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-1.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {running ? 'Categorising…' : 'Categorise Now'}
                    </button>
                  </div>
                </div>
              )}

              {/* How it works */}
              <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-brand-border">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">How it works</p>
                  <p className="text-[10px] font-mono text-brand-muted mt-0.5">Every transaction follows this fixed execution flow — no step can be skipped</p>
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

              {/* Capabilities */}
              <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-brand-border">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Capabilities</p>
                  <p className="text-[10px] font-mono text-brand-muted mt-0.5">What this agent does once deployed and connected to your data</p>
                </div>
                <motion.ul variants={capabilityVariants} initial="hidden" animate="show" className="divide-y divide-brand-border">
                  {CAPABILITIES.map(cap => (
                    <motion.li key={cap} variants={capItemVariants} className="flex items-start gap-3 px-4 py-3">
                      <span className="text-brand-muted font-mono text-[10px] mt-0.5 shrink-0">→</span>
                      <span className="text-xs font-mono text-brand-secondary">{cap}</span>
                    </motion.li>
                  ))}
                </motion.ul>
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
                      <p className="text-[10px] font-mono text-brand-muted">
                        {deployed.status === 'active' ? 'Agent is live and processing' : 'Agent is paused — no runs will fire'}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'transactions' && (
            <TransactionsTab
              transactions={transactions}
              total={listTotal}
              offset={offset}
              loadingMore={loadingMore}
              filter={filter}
              counts={counts}
              categories={categories}
              running={running}
              deployedId={deployed?.id ?? null}
              pendingCount={pendingCount}
              onFilterChange={setFilter}
              onCategoryUpdate={handleCategoryUpdate}
              onCategoriseNow={handleCategoriseNow}
              onExportCsv={handleExportCsv}
              onLoadMore={handleLoadMore}
            />
          )}

          {activeTab === 'month-end-close' && <MonthEndCloseTab toolId={deployed?.id ?? null} />}
          {activeTab === 'payroll' && <PayrollRecTab toolId={deployed?.id ?? null} />}
          {activeTab === 'journal-entries' && <JournalEntriesTab toolId={deployed?.id ?? null} />}
          {activeTab === 'executions' && <ToolExecutionsTab toolId={deployed?.id ?? null} />}
          {activeTab === 'approvals' && <ToolApprovalsTab toolId={deployed?.id ?? null} />}
          {activeTab === 'audit' && <ToolAuditTab toolId={deployed?.id ?? null} />}
        </motion.div>
      </AnimatePresence>

      {showConfig && (
        <ConfigDrawer
          tool={deployed}
          toolType="ai_accountant"
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); fetchDeployed() }}
        />
      )}
    </motion.div>
  )
}
