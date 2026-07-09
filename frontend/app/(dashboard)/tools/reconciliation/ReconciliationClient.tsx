'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { useCurrency, useToast } from '@/components/Providers'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import { ReconciliationRun, ReconciliationItem } from './types'
import { RunControls } from './RunControls'
import { RunHistory } from './RunHistory'
import { ReconciliationVisual } from './ReconciliationVisual'
import { ReconciliationTable } from './ReconciliationTable'
import { ReconcileAllSection } from './ReconcileAllSection'
import { PayrollRecSection } from './PayrollRecSection'
import { InvoiceRecSection } from './InvoiceRecSection'
import { VatRecSection } from './VatRecSection'
import { TOOLS } from '../tools-data'
import { motion, AnimatePresence } from 'framer-motion'
import { CreateJournalEntryModal, type JournalEntrySuggestion } from '@/components/dashboard/tools/CreateJournalEntryModal'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'



const REC_TYPES: { key: string; label: string }[] = [
  { key: 'all',     label: 'All' },
  { key: 'bank',    label: 'Bank' },
  { key: 'payroll', label: 'Payroll' },
  { key: 'invoice', label: 'Invoice' },
  { key: 'vat',     label: 'VAT' },
]

function defaultPeriodStart() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10)
}
function defaultPeriodEnd() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().slice(0, 10)
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

const HOW_IT_WORKS = [
  { step: '01', label: 'Connect',        desc: 'Link your bank accounts (Plaid, TrueLayer) and accounting software (Xero, QuickBooks, FreshBooks). Clendan pulls live data from all of them.' },
  { step: '02', label: 'Pick a period',  desc: 'Choose a month. One click runs Bank, Invoice, and VAT reconciliations in parallel - no setup needed per run.' },
  { step: '03', label: 'Review',         desc: 'Summary cards show matched transactions, outstanding invoices, VAT position, and any flagged items that need your attention.' },
  { step: '04', label: 'Act',            desc: 'Create journal entries for unmatched items, investigate flagged invoices, export results to CSV, or drill into any rec type for the full detail.' },
]

const WHAT_IS_COVERED = [
  {
    key: 'bank',
    label: 'Bank',
    color: '#00a8cc',
    desc: 'Matches every transaction in your bank accounts against invoices and bills in your accounting system. Flags payments with no matching record - catches fraud, duplicates, and missing invoices.',
  },
  {
    key: 'invoice',
    label: 'Invoice',
    color: '#f5a623',
    desc: 'Reviews all sales invoices for the period. Surfaces invoices that are overdue, missing tax, or still outstanding. Gives you the total tax collected and what remains unpaid.',
  },
  {
    key: 'vat',
    label: 'VAT',
    color: '#00C853',
    desc: 'Totals the VAT recorded on your sales invoices and flags any invoice where tax is missing. Acts as a pre-filing sanity check so you know exactly what you owe HMRC before submitting.',
  },
  {
    key: 'payroll',
    label: 'Payroll',
    color: '#a78bfa',
    desc: 'Cross-references payroll payments from your bank against your employee roster. Detects ghost employees (payments to unknown names), missing payments, and salary discrepancies.',
  },
]

export function ReconciliationClient() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const { currency } = useCurrency()
  const { toast } = useToast()
  const router = useRouter()
  const [showOverview, setShowOverview] = useState(false)
  const [recType, setRecType] = useState<'all' | 'bank' | 'payroll' | 'invoice' | 'vat'>('all')
  const recTypeSelectorRef = useRef<HTMLDivElement>(null)
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
  const [jeSuggestion, setJeSuggestion] = useState<JournalEntrySuggestion | null>(null)
  const [fetchingJE, setFetchingJE] = useState(false)

  const fetchDeployed = useCallback(async () => {
    const token = await getToken()
    const res = await fetch(`${API}/tools`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return
    const json = await res.json()
    const tools: Tool[] = json.data?.tools ?? json.data ?? []
    setDeployed(tools.find((w) => w.type === 'reconciliation') ?? null)
  }, [getToken])

  const fetchRuns = useCallback(async () => {
    const token = await getToken()
    const res = await fetch(`${API}/reconciliation/runs?limit=20`, {
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
      const res = await fetch(`${API}/reconciliation/runs/${runId}/items`, {
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
        toast('Reconciliation complete', 'success')
      }
    }, 2000)
    const timeout = setTimeout(() => {
      active = false
      setPolling(false)
      setRunning(false)
      toast('Reconciliation timed out - check back shortly', 'error')
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
      const toolsRes = await fetch(`${API}/tools`, { headers: { Authorization: `Bearer ${token}` } })
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
          body: JSON.stringify({ type: 'reconciliation', config: getDefaultConfig('reconciliation') }),
        })
      }
      await fetchDeployed()
    } finally {
      setDeploying(false)
    }
  }

  async function handleRun() {
    if (!deployed?.id) { toast('Deploy the tool to continue', 'error'); return }
    if (running) return
    setRunning(true)
    try {
      const token = await getToken()
      const cfg = (deployed.config_json as Record<string, unknown> | null)
      const configAccountIds = cfg?.account_ids
      const runAccountIds = Array.isArray(configAccountIds) && configAccountIds.length > 0 ? configAccountIds as string[] : null
      const configIntegrationSources = cfg?.integration_sources
      const runIntegrationSources = Array.isArray(configIntegrationSources) && configIntegrationSources.length > 0 ? configIntegrationSources as string[] : null
      const res = await fetch(`${API}/reconciliation/run`, {
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

  async function handleCreateJE() {
    if (!selectedRun) return
    setFetchingJE(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/journal-entries/suggest/reconciliation-run/${selectedRun.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { toast('Failed to load suggestion', 'error'); return }
      const json = await res.json()
      setModalOpen(false)
      setJeSuggestion(json.data?.suggestion ?? null)
    } catch {
      toast('Network error', 'error')
    } finally {
      setFetchingJE(false)
    }
  }

  async function handleExport(runId: string) {
    const token = await getToken()
    const params = new URLSearchParams()
    if (currency && currency !== 'GBP') params.set('display_currency', currency)
    const res = await fetch(`${API}/reconciliation/runs/${runId}/export?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) { toast('Export failed - please try again', 'error'); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `reconciliation_${runId}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const isActive = deployed?.status === 'active'
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
            <h1 className="font-heading font-bold text-2xl text-brand-text">Reconciliation</h1>
          </div>
          <p className="text-xs font-body text-brand-muted">
            Match transactions against source records. Detects anomalies and flags discrepancies across Bank and Payroll.
          </p>
        </div>
        {canConfigure && (
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setShowOverview(true)}
              className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors">
              Overview
            </button>
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

      {/* Reconcile Content - only once deployed, matching the other tools' undeployed state */}
      {deployed ? (
      <motion.div variants={sectionVariants} className="space-y-4 mt-6">
        {/* Rec type selector */}
        <div ref={recTypeSelectorRef} className="flex items-center gap-1 p-1 bg-brand-elevated border border-brand-border rounded-sm w-fit">
          {REC_TYPES.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setRecType(key as any)}
              className={`text-[11px] font-body px-3 py-1.5 rounded-[2px] transition-colors ${
                recType === key
                  ? 'bg-brand-surface text-brand-text border border-brand-border'
                  : 'text-brand-muted hover:text-brand-text'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Run all */}
        {recType === 'all' && (
          <ReconcileAllSection
            toolId={deployed?.id ?? null}
            onViewAudit={() => router.push('/audit')}
          />
        )}

        {/* Bank reconciliation */}
        {recType === 'bank' && (
          <>
            <RunControls
              periodStart={periodStart}
              periodEnd={periodEnd}
              toolReady={!!deployed?.id}
              running={running}
              onPeriodStartChange={setPeriodStart}
              onPeriodEndChange={setPeriodEnd}
              onRun={handleRun}
            />
            {selectedRun && (
              <div className="mt-5">
                <ReconciliationVisual run={selectedRun} />
              </div>
            )}
            <div className="space-y-2 mt-5">
              <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Run History</p>
              <RunHistory
                runs={runs}
                loading={runsLoading}
                selectedId={selectedRun?.id ?? null}
                onSelect={(r) => { setSelectedRun(r); fetchItems(r.id); setModalOpen(true) }}
              />
            </div>
          </>
        )}

        {/* Payroll reconciliation */}
        {recType === 'payroll' && (
          <PayrollRecSection toolId={deployed?.id ?? null} />
        )}

        {/* Invoice reconciliation */}
        {recType === 'invoice' && (
          <InvoiceRecSection toolId={deployed?.id ?? null} />
        )}

        {/* VAT reconciliation */}
        {recType === 'vat' && (
          <VatRecSection toolId={deployed?.id ?? null} />
        )}
      </motion.div>
      ) : (
        <motion.div variants={sectionVariants} className="mt-6">
          <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-16 text-center space-y-2">
            <p className="text-xs font-body text-brand-secondary">This agent is not deployed yet.</p>
            <p className="text-[11px] font-body text-brand-muted">
              Deploy it to start reconciling and see its activity here. Requires connected Banking · Accounting integrations.
            </p>
          </div>
        </motion.div>
      )}

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
                {/* How it works */}
                <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">How it works</p>
                    <p className="text-[11px] font-body text-brand-muted mt-0.5">Connect your data, pick a month, review results - that&apos;s it</p>
                  </div>
                  <div className="grid grid-cols-1 divide-y divide-brand-border">
                    {HOW_IT_WORKS.map(({ step, label, desc }) => (
                      <div key={step} className="px-4 py-3 space-y-1.5 flex gap-4">
                        <p className="text-[11px] font-body text-brand-muted font-mono">{step}</p>
                        <div>
                          <p className="text-xs font-body font-medium text-brand-text">{label}</p>
                          <p className="text-[11px] font-body text-brand-muted leading-relaxed mt-0.5">{desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* What's covered */}
                <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">What&apos;s covered</p>
                    <p className="text-[11px] font-body text-brand-muted mt-0.5">Four reconciliation types - run all at once or drill into each individually</p>
                  </div>
                  <div className="grid grid-cols-1 divide-y divide-brand-border">
                    {WHAT_IS_COVERED.map(({ key, label, color, desc }) => (
                      <div key={key} className="px-4 py-3 space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ background: color }} />
                          <p className="text-xs font-body font-medium text-brand-text">{label}</p>
                        </div>
                        <p className="text-[11px] font-body text-brand-muted leading-relaxed">{desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Configuration */}
                {deployed && (
                  <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                    <div className="px-4 py-3 border-b border-brand-border">
                      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Configuration</p>
                    </div>
                    <div className="px-4 py-4 space-y-4">
                      <div className="space-y-1.5">
                        <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Status</p>
                        <p className="text-xs font-body text-brand-text">{deployed.status === 'active' ? 'Running' : 'Paused'}</p>
                        <p className="text-[11px] font-body text-brand-muted">{deployed.status === 'active' ? 'Agent is live and processing' : 'Agent is paused - no runs will fire'}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Capabilities */}
                <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Capabilities</p>
                    <p className="text-[11px] font-body text-brand-muted mt-0.5">What this agent does once deployed and connected to your data</p>
                  </div>
                  <ul className="divide-y divide-brand-border">
                    {RECONCILIATION_CAPABILITIES.map(cap => (
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
          toolType="reconciliation"
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); fetchDeployed() }}
        />
      )}

      <CreateJournalEntryModal
        suggestion={jeSuggestion}
        onClose={() => setJeSuggestion(null)}
        onCreated={() => setJeSuggestion(null)}
      />

      {/* Bank rec results modal */}
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
                  <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">
                    Results · {new Date(selectedRun.period_start).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })} – {new Date(selectedRun.period_end).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </p>
                  {selectedRun.triggered_by_email && (
                    <p className="text-[11px] font-body text-brand-muted">
                      by {selectedRun.triggered_by_email}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCreateJE}
                    disabled={fetchingJE}
                    className="text-[11px] font-body bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 transition-all disabled:opacity-40"
                  >
                    {fetchingJE ? 'Loading…' : 'Create Journal Entry'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    className="text-brand-muted hover:text-brand-text transition-colors"
                  >
                    <span className="text-lg leading-none">✕</span>
                  </button>
                </div>
              </div>
              <ReconciliationTable items={items} loading={itemsLoading} runId={selectedRun.id} onExport={handleExport} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
