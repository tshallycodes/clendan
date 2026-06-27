'use client'

import { useState, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface RosterEmployee {
  name: string
  expectedSalary: string // display value, converted to minor on submit
}

interface PayrollRun {
  id: string
  period: string
  status: 'pending' | 'clean' | 'flagged' | 'blocked'
  matched_count: number
  ghost_count: number
  missing_count: number
  discrepancy_count: number
  total_payroll_minor: number
  created_at: string
}

interface GhostRow {
  transaction_id: string
  description: string
  amount_minor: number
  date: string
  extracted_name: string
}

interface MissingRow {
  name: string
  expected_minor: number
}

interface DiscrepancyRow {
  name: string
  expected_minor: number
  actual_minor: number
  diff_pct: number
  transaction_id: string
}

interface RunResults {
  ghosts: GhostRow[]
  missing: MissingRow[]
  discrepancies: DiscrepancyRow[]
  matched: { transaction_id: string }[]
}

const STATUS_STYLE: Record<string, string> = {
  clean:   'text-[#00C853] bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)]',
  flagged: 'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[rgba(255,77,109,0.2)]',
  blocked: 'text-[#ff4d6d] bg-[rgba(255,77,109,0.08)] border border-[rgba(255,77,109,0.2)]',
  pending: 'text-[#f5a623] bg-[rgba(245,166,35,0.08)] border border-[rgba(245,166,35,0.2)]',
}

function formatMinor(minor: number, symbol: string): string {
  return `${symbol}${(minor / 100).toFixed(2)}`
}

function GhostTable({ rows, symbol }: { rows: GhostRow[]; symbol: string }) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-mono uppercase tracking-widest text-[#ff4d6d]">Ghost Employees ({rows.length})</p>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-brand-border">
              {['Extracted Name', 'Description', 'Amount', 'Date'].map(h => (
                <th key={h} className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-4 py-2.5 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.transaction_id} className="border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors">
                <td className="px-4 py-2.5 text-xs font-mono text-[#ff4d6d]">{r.extracted_name || '—'}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-brand-text max-w-[240px] truncate">{r.description}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-brand-text">{formatMinor(r.amount_minor, symbol)}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-brand-muted">{r.date.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MissingTable({ rows, symbol }: { rows: MissingRow[]; symbol: string }) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-mono uppercase tracking-widest text-[#f5a623]">Missing Employees ({rows.length})</p>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-brand-border">
              {['Name', 'Expected Salary'].map(h => (
                <th key={h} className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-4 py-2.5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.name} className="border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors">
                <td className="px-4 py-2.5 text-xs font-mono text-[#f5a623]">{r.name}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-brand-text">{formatMinor(r.expected_minor, symbol)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DiscrepancyTable({ rows, symbol }: { rows: DiscrepancyRow[]; symbol: string }) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-mono uppercase tracking-widest text-[#f5a623]">Amount Discrepancies ({rows.length})</p>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-brand-border">
              {['Name', 'Expected', 'Actual', 'Diff %'].map(h => (
                <th key={h} className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-4 py-2.5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.transaction_id} className="border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors">
                <td className="px-4 py-2.5 text-xs font-mono text-brand-text">{r.name}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-brand-muted">{formatMinor(r.expected_minor, symbol)}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-brand-text">{formatMinor(r.actual_minor, symbol)}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-[#f5a623]">{r.diff_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function PayrollRecTab({ toolId }: { toolId: string | null }) {
  const { getToken } = useAuth()
  const { currency } = useCurrency()
  const currencySymbol = CURRENCY_MAP[currency]?.symbol ?? currency

  const [period, setPeriod] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  })
  const [roster, setRoster] = useState<RosterEmployee[]>([{ name: '', expectedSalary: '' }])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [activeRun, setActiveRun] = useState<PayrollRun | null>(null)
  const [results, setResults] = useState<RunResults | null>(null)
  const [history, setHistory] = useState<PayrollRun[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)

  const loadHistory = useCallback(async () => {
    if (historyLoaded) return
    setLoadingHistory(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/payroll-runs`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) {
        const json = await res.json()
        setHistory(json.data?.runs ?? [])
      }
    } finally {
      setLoadingHistory(false)
      setHistoryLoaded(true)
    }
  }, [getToken, historyLoaded])

  function addEmployee() {
    setRoster(prev => [...prev, { name: '', expectedSalary: '' }])
  }

  function updateEmployee(index: number, field: keyof RosterEmployee, value: string) {
    setRoster(prev => prev.map((e, i) => i === index ? { ...e, [field]: value } : e))
  }

  function removeEmployee(index: number) {
    setRoster(prev => prev.filter((_, i) => i !== index))
  }

  const validRoster = roster.filter(e => e.name.trim() && e.expectedSalary.trim())
  const canRun = !!toolId && validRoster.length > 0 && !running

  async function handleRun() {
    if (!canRun || !toolId) return
    setRunning(true)
    setError(null)
    try {
      const token = await getToken()
      const rosterPayload = validRoster.map(e => ({
        name: e.name.trim(),
        expected_minor: Math.round(parseFloat(e.expectedSalary) * 100),
      }))
      const res = await fetch(`${API}/v1/payroll-runs`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `payroll-rec-${toolId}-${period}-${Date.now()}`,
        },
        body: JSON.stringify({ period, roster: rosterPayload, tool_id: toolId }),
      })
      const json = await res.json()
      if (!res.ok) { setError(json.detail ?? `Error ${res.status}`); return }

      const runId: string = json.data?.run_id
      // Poll until complete
      let attempts = 0
      while (attempts < 30) {
        await new Promise(r => setTimeout(r, 2000))
        const poll = await fetch(`${API}/v1/payroll-runs/${runId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (poll.ok) {
          const pollJson = await poll.json()
          const run: PayrollRun & { results_json: RunResults } = pollJson.data
          if (run.status !== 'pending') {
            setActiveRun(run)
            setResults(run.results_json ?? null)
            setHistoryLoaded(false)
            break
          }
        }
        attempts++
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error')
    } finally {
      setRunning(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-5"
    >
      {/* Period + Roster builder */}
      <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-4">
        <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Run Payroll Reconciliation</p>

        <div className="flex items-center gap-4 flex-wrap">
          <div className="space-y-1">
            <label className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Period</label>
            <input
              type="month"
              value={period}
              onChange={e => setPeriod(e.target.value)}
              className="bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text text-xs font-mono rounded-sm px-3 py-2 outline-none transition-colors"
            />
          </div>
        </div>

        {/* Roster table */}
        <div className="space-y-2">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Employee Roster</p>
          <div className="space-y-1">
            {roster.map((emp, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Employee name"
                  value={emp.name}
                  onChange={e => updateEmployee(i, 'name', e.target.value)}
                  className="flex-1 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted text-xs font-mono rounded-sm px-3 py-2 outline-none transition-colors"
                />
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-mono text-brand-muted pointer-events-none">{currencySymbol}</span>
                  <input
                    type="number"
                    placeholder="Monthly salary"
                    value={emp.expectedSalary}
                    onChange={e => updateEmployee(i, 'expectedSalary', e.target.value)}
                    className="w-40 bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted text-xs font-mono rounded-sm pl-7 pr-3 py-2 outline-none transition-colors"
                  />
                </div>
                {roster.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeEmployee(i)}
                    className="text-[10px] font-mono text-brand-muted hover:text-[#ff4d6d] transition-colors px-2"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addEmployee}
            className="text-[10px] font-mono text-brand-muted hover:text-brand-text border border-brand-border rounded-sm px-3 py-1.5 transition-colors"
          >
            + Add Employee
          </button>
        </div>

        {error && <p className="text-xs font-mono text-[#ff4d6d]">{error}</p>}

        <button
          type="button"
          onClick={handleRun}
          disabled={!canRun}
          className="bg-[#00C853] text-black text-xs font-mono rounded-sm px-4 py-2 hover:bg-[#00a844] active:scale-[0.97] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {running ? 'Running…' : 'Run Payroll Rec'}
        </button>
      </div>

      {/* Results panel */}
      <AnimatePresence>
        {activeRun && results && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm uppercase tracking-wider ${STATUS_STYLE[activeRun.status]}`}>
                  {activeRun.status}
                </span>
                <span className="text-[10px] font-mono text-brand-muted">{activeRun.period}</span>
              </div>
              <div className="flex gap-3 flex-wrap">
                <span className="text-[10px] font-mono px-2 py-1 rounded-sm bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]">
                  Matched {activeRun.matched_count}
                </span>
                <span className="text-[10px] font-mono px-2 py-1 rounded-sm bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]">
                  Ghosts {activeRun.ghost_count}
                </span>
                <span className="text-[10px] font-mono px-2 py-1 rounded-sm bg-[rgba(245,166,35,0.08)] text-[#f5a623] border border-[rgba(245,166,35,0.2)]">
                  Missing {activeRun.missing_count}
                </span>
              </div>
            </div>

            <GhostTable rows={results.ghosts ?? []} symbol={currencySymbol} />
            <MissingTable rows={results.missing ?? []} symbol={currencySymbol} />
            <DiscrepancyTable rows={results.discrepancies ?? []} symbol={currencySymbol} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Run history */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Run History</p>
          {!historyLoaded && (
            <button
              type="button"
              onClick={loadHistory}
              disabled={loadingHistory}
              className="text-[10px] font-mono text-brand-muted hover:text-brand-text border border-brand-border rounded-sm px-3 py-1 transition-colors disabled:opacity-50"
            >
              {loadingHistory ? 'Loading…' : 'Load history'}
            </button>
          )}
        </div>
        {history.length > 0 && (
          <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
            {history.map(r => (
              <div key={r.id} className="flex items-center justify-between px-4 py-3 border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors">
                <span className="text-xs font-mono text-brand-text">{r.period}</span>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-mono text-brand-muted">
                    {r.ghost_count > 0 && <span className="text-[#ff4d6d] mr-2">{r.ghost_count} ghosts</span>}
                    {r.missing_count > 0 && <span className="text-[#f5a623]">{r.missing_count} missing</span>}
                  </span>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${STATUS_STYLE[r.status] ?? STATUS_STYLE.pending}`}>
                    {r.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
        {historyLoaded && history.length === 0 && (
          <p className="text-xs font-mono text-brand-muted">No runs yet.</p>
        )}
      </div>
    </motion.div>
  )
}
