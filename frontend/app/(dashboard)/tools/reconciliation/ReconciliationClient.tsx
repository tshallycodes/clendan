'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { ReconciliationRun, ReconciliationItem } from './types'
import { RunControls } from './RunControls'
import { RunHistory } from './RunHistory'
import { ReconciliationTable } from './ReconciliationTable'
import { ToolExecutionsTab } from '@/components/dashboard/tools/ToolExecutionsTab'
import { ToolApprovalsTab } from '@/components/dashboard/tools/ToolApprovalsTab'
import { ToolAuditTab } from '@/components/dashboard/tools/ToolAuditTab'

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
  selectedRun: ReconciliationRun | null
  items: ReconciliationItem[]
  itemsLoading: boolean
  onPeriodStartChange: (v: string) => void
  onPeriodEndChange: (v: string) => void
  onRun: () => void
  onSelectRun: (run: ReconciliationRun) => void
  onExport: (runId: string) => void
}

function OverviewTab({
  periodStart, periodEnd, toolId, running,
  runs, runsLoading, selectedRun, items, itemsLoading,
  onPeriodStartChange, onPeriodEndChange, onRun, onSelectRun, onExport,
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

export function ReconciliationClient() {
  const { getToken } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [runs, setRuns] = useState<ReconciliationRun[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [selectedRun, setSelectedRun] = useState<ReconciliationRun | null>(null)
  const [items, setItems] = useState<ReconciliationItem[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)
  const [periodStart, setPeriodStart] = useState(defaultPeriodStart)
  const [periodEnd, setPeriodEnd] = useState(defaultPeriodEnd)
  const [toolId, setToolId] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

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
      const toolsRes = await fetch(`${API}/v1/tools`, { headers: { Authorization: `Bearer ${token}` } })
      if (toolsRes.ok) {
        const toolsJson = await toolsRes.json()
        const tools: { id: string; type: string }[] = toolsJson.data?.tools ?? toolsJson.data ?? []
        const rec = tools.find((w) => w.type === 'reconciliation')
        if (rec) setToolId(rec.id)
      }
      setRunsLoading(true)
      const list = await fetchRuns()
      setRunsLoading(false)
      if (list?.[0]) { setSelectedRun(list[0]); fetchItems(list[0].id) }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRun() {
    if (!toolId || running) return
    setRunning(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/reconciliation/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_start: periodStart, period_end: periodEnd, tool_id: toolId }),
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

  return (
    <div className="p-6 space-y-5">
      <Link href="/tools" className="text-[11px] font-mono text-brand-muted hover:text-brand-secondary transition-colors">
        ← Tools
      </Link>

      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Reconciliation</h1>
        <p className="text-[10px] font-mono text-brand-muted mt-1 uppercase tracking-widest">
          Match bank transactions against invoices
        </p>
      </div>

      <div className="flex gap-1 border-b border-brand-border">
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
      </div>

      {activeTab === 'overview' && (
        <OverviewTab
          periodStart={periodStart} periodEnd={periodEnd} toolId={toolId} running={running}
          runs={runs} runsLoading={runsLoading} selectedRun={selectedRun}
          items={items} itemsLoading={itemsLoading}
          onPeriodStartChange={setPeriodStart} onPeriodEndChange={setPeriodEnd}
          onRun={handleRun} onSelectRun={(r) => { setSelectedRun(r); fetchItems(r.id) }}
          onExport={handleExport}
        />
      )}
      {activeTab === 'executions' && toolId && <ToolExecutionsTab toolId={toolId} />}
      {activeTab === 'approvals' && toolId && <ToolApprovalsTab toolId={toolId} />}
      {activeTab === 'audit' && toolId && <ToolAuditTab toolId={toolId} />}
    </div>
  )
}
