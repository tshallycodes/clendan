'use client'

import { useState, useCallback, useMemo, useRef } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion, AnimatePresence } from 'framer-motion'
import { useCurrency, useToast } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { MonthPicker } from './MonthPicker'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ParsedEmployee {
  name: string
  expected_minor: number
  raw: string
  error?: string
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

function parseRosterText(text: string): ParsedEmployee[] {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0 && !line.startsWith('#'))
    .map(raw => {
      const comma = raw.lastIndexOf(',')
      if (comma === -1) return { name: '', expected_minor: 0, raw, error: 'Missing comma — use: Name, Salary' }
      const name = raw.slice(0, comma).trim()
      const salaryStr = raw.slice(comma + 1).trim().replace(/[,\s]/g, '')
      const salary = parseFloat(salaryStr)
      if (!name) return { name: '', expected_minor: 0, raw, error: 'Name is empty' }
      if (isNaN(salary) || salary <= 0) return { name, expected_minor: 0, raw, error: `Invalid salary: "${raw.slice(comma + 1).trim()}"` }
      return { name, expected_minor: Math.round(salary * 100), raw }
    })
}

function GhostTable({ rows, symbol }: { rows: GhostRow[]; symbol: string }) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-body uppercase tracking-widest text-[#ff4d6d]">Ghost Employees ({rows.length})</p>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-brand-border">
              {['Extracted Name', 'Description', 'Amount', 'Date'].map(h => (
                <th key={h} className="text-left text-[10px] font-body text-brand-muted uppercase tracking-widest px-4 py-2.5 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.transaction_id} className="border-b border-brand-border last:border-0 hover:bg-brand-bg transition-colors">
                <td className="px-4 py-2.5 text-xs font-body text-[#ff4d6d]">{r.extracted_name || '—'}</td>
                <td className="px-4 py-2.5 text-xs font-body text-brand-text max-w-[240px] truncate">{r.description}</td>
                <td className="px-4 py-2.5 text-xs font-body text-brand-text">{formatMinor(r.amount_minor, symbol)}</td>
                <td className="px-4 py-2.5 text-xs font-body text-brand-muted">{r.date.slice(0, 10)}</td>
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
      <p className="text-[10px] font-body uppercase tracking-widest text-[#f5a623]">Missing Employees ({rows.length})</p>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-brand-border">
              {['Name', 'Expected Salary'].map(h => (
                <th key={h} className="text-left text-[10px] font-body text-brand-muted uppercase tracking-widest px-4 py-2.5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.name} className="border-b border-brand-border last:border-0 hover:bg-brand-bg transition-colors">
                <td className="px-4 py-2.5 text-xs font-body text-[#f5a623]">{r.name}</td>
                <td className="px-4 py-2.5 text-xs font-body text-brand-text">{formatMinor(r.expected_minor, symbol)}</td>
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
      <p className="text-[10px] font-body uppercase tracking-widest text-[#f5a623]">Amount Discrepancies ({rows.length})</p>
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-brand-border">
              {['Name', 'Expected', 'Actual', 'Diff %'].map(h => (
                <th key={h} className="text-left text-[10px] font-body text-brand-muted uppercase tracking-widest px-4 py-2.5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.transaction_id} className="border-b border-brand-border last:border-0 hover:bg-brand-bg transition-colors">
                <td className="px-4 py-2.5 text-xs font-body text-brand-text">{r.name}</td>
                <td className="px-4 py-2.5 text-xs font-body text-brand-muted">{formatMinor(r.expected_minor, symbol)}</td>
                <td className="px-4 py-2.5 text-xs font-body text-brand-text">{formatMinor(r.actual_minor, symbol)}</td>
                <td className="px-4 py-2.5 text-xs font-body text-[#f5a623]">{r.diff_pct.toFixed(1)}%</td>
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
  const { toast } = useToast()

  const [period, setPeriod] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  })
  const [rosterText, setRosterText] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [activeRun, setActiveRun] = useState<PayrollRun | null>(null)
  const [results, setResults] = useState<RunResults | null>(null)
  const [exporting, setExporting] = useState(false)
  const [history, setHistory] = useState<PayrollRun[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const parsed = useMemo(() => parseRosterText(rosterText), [rosterText])
  const parseErrors = parsed.filter(p => p.error)
  const validRoster = parsed.filter(p => !p.error)
  const rosterReady = validRoster.length > 0 && parseErrors.length === 0 && !running
  const canRun = !!toolId && rosterReady

  const loadHistory = useCallback(async () => {
    if (historyLoaded) return
    setLoadingHistory(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/payroll-runs`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) {
        const json = await res.json()
        setHistory(json.data?.runs ?? [])
      }
    } finally {
      setLoadingHistory(false)
      setHistoryLoaded(true)
    }
  }, [getToken, historyLoaded])

  function handleCsvImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const text = ev.target?.result as string
      const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
      // Detect header row — skip if first cell is non-numeric name-like header
      const start = /^(name|employee|full\s*name|staff)/i.test(lines[0]?.split(',')[0] ?? '') ? 1 : 0
      const normalised = lines.slice(start).map(line => {
        const cols = line.split(',').map(c => c.trim().replace(/^"|"$/g, ''))
        // Support: Name, Salary  OR  Name, Salary, ...extra columns ignored
        if (cols.length < 2) return line
        const name = cols[0]
        // Find first numeric-looking column after name
        const salary = cols.slice(1).find(c => /^[\d.]+$/.test(c.replace(/[,\s]/g, ''))) ?? cols[1]
        return `${name}, ${salary}`
      })
      setRosterText(normalised.join('\n'))
      // Reset so the same file can be re-imported
      e.target.value = ''
    }
    reader.readAsText(file)
  }

  async function handleExport() {
    if (!activeRun) return
    setExporting(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/payroll-runs/${activeRun.id}/export`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { toast('Export failed — please try again', 'error'); return }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `payroll_rec_${activeRun.period}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast('Export downloaded', 'success')
    } finally {
      setExporting(false)
    }
  }

  async function handleRun() {
    if (!toolId) { toast('Deploy the tool to continue', 'error'); return }
    if (!canRun) return
    setRunning(true)
    setError(null)
    try {
      const token = await getToken()
      const rosterPayload = validRoster.map(e => ({ name: e.name, expected_minor: e.expected_minor }))
      const res = await fetch(`${API}/payroll-runs`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `payroll-rec-${toolId}-${period}-${Date.now()}`,
        },
        body: JSON.stringify({ period, roster: rosterPayload, tool_id: toolId }),
      })
      const json = await res.json()
      if (!res.ok) { setError(json.detail ?? `Error ${res.status}`); toast(json.detail ?? 'Run failed', 'error'); return }

      const runId: string = json.data?.run_id
      let attempts = 0
      let completed = false
      while (attempts < 30) {
        await new Promise(r => setTimeout(r, 2000))
        const poll = await fetch(`${API}/payroll-runs/${runId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (poll.ok) {
          const pollJson = await poll.json()
          const run: PayrollRun & { results_json: RunResults } = pollJson.data
          if (run.status !== 'pending') {
            setActiveRun(run)
            setResults(run.results_json ?? null)
            setHistoryLoaded(false)
            completed = true
            const issues = (run.ghost_count ?? 0) + (run.missing_count ?? 0) + (run.discrepancy_count ?? 0)
            toast(issues > 0 ? `Rec complete — ${issues} issue${issues !== 1 ? 's' : ''} found` : 'Payroll rec complete — all clear', issues > 0 ? 'info' : 'success')
            break
          }
        }
        attempts++
      }
      if (!completed) toast('Rec timed out — check back shortly', 'error')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Network error'
      setError(msg)
      toast(msg, 'error')
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
      {/* Config card */}
      <div className="bg-brand-surface border border-brand-border rounded-sm p-4 space-y-4">
        <p className="text-[10px] font-body uppercase tracking-widest text-brand-muted">Run Payroll Reconciliation</p>

        {/* Period */}
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-body text-brand-muted uppercase tracking-widest">Period</label>
          <MonthPicker value={period} onChange={setPeriod} />
        </div>

        {/* Roster — bulk paste or CSV import */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <label className="text-[10px] font-body text-brand-muted uppercase tracking-widest">Employee Roster</label>
            <div className="flex items-center gap-2">
              {validRoster.length > 0 && parseErrors.length === 0 && (
                <span className="text-[10px] font-body text-[#00C853]">{validRoster.length} employee{validRoster.length !== 1 ? 's' : ''} ready</span>
              )}
              {parseErrors.length > 0 && (
                <span className="text-[10px] font-body text-[#ff4d6d]">{parseErrors.length} line{parseErrors.length !== 1 ? 's' : ''} with errors</span>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={handleCsvImport}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-[10px] font-body border border-brand-border text-brand-muted hover:text-brand-text rounded-sm px-2.5 py-1 transition-colors"
              >
                Import CSV
              </button>
            </div>
          </div>
          <textarea
            rows={8}
            value={rosterText}
            onChange={e => setRosterText(e.target.value)}
            placeholder={`Paste your roster — one employee per line:\n\nJane Smith, 5000\nBob Jones, 4500\nAlice Chen, 6200\n\nFormat: Name, Monthly salary`}
            className="w-full bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted text-xs font-body rounded-sm px-3 py-2.5 outline-none transition-colors resize-y leading-relaxed"
          />
          {parseErrors.length > 0 && (
            <div className="space-y-1">
              {parseErrors.map((e, i) => (
                <p key={i} className="text-[10px] font-body text-[#ff4d6d]">
                  Line {parsed.indexOf(e) + 1}: {e.error} — <span className="text-brand-muted">{e.raw}</span>
                </p>
              ))}
            </div>
          )}
        </div>

        {error && <p className="text-xs font-body text-[#ff4d6d]">{error}</p>}

        <button
          type="button"
          onClick={handleRun}
          disabled={!rosterReady}
          className="bg-[#00C853] text-black text-xs font-body rounded-sm px-4 py-2 hover:bg-[#00a844] active:scale-[0.97] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
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
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-3">
                  <span className={`text-[10px] font-body px-2 py-0.5 rounded-sm uppercase tracking-wider ${STATUS_STYLE[activeRun.status]}`}>
                    {activeRun.status}
                  </span>
                  <span className="text-[10px] font-body text-brand-muted">{activeRun.period}</span>
                </div>
                <button
                  type="button"
                  onClick={handleExport}
                  disabled={exporting}
                  className="text-[10px] font-body border border-brand-border text-brand-muted hover:text-brand-text rounded-sm px-3 py-1 transition-colors disabled:opacity-40"
                >
                  {exporting ? 'Exporting…' : 'Export CSV'}
                </button>
              </div>
              <div className="flex gap-3 flex-wrap">
                <span className="text-[10px] font-body px-2 py-1 rounded-sm bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]">
                  Matched {activeRun.matched_count}
                </span>
                <span className="text-[10px] font-body px-2 py-1 rounded-sm bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]">
                  Ghosts {activeRun.ghost_count}
                </span>
                <span className="text-[10px] font-body px-2 py-1 rounded-sm bg-[rgba(245,166,35,0.08)] text-[#f5a623] border border-[rgba(245,166,35,0.2)]">
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
          <p className="text-[10px] font-body uppercase tracking-widest text-brand-muted">Run History</p>
          {!historyLoaded && (
            <button
              type="button"
              onClick={loadHistory}
              disabled={loadingHistory}
              className="text-[10px] font-body text-brand-muted hover:text-brand-text border border-brand-border rounded-sm px-3 py-1 transition-colors disabled:opacity-50"
            >
              {loadingHistory ? 'Loading…' : 'Load history'}
            </button>
          )}
        </div>
        {history.length > 0 && (
          <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
            {history.map(r => (
              <div key={r.id} className="flex items-center justify-between px-4 py-3 border-b border-brand-border last:border-0 hover:bg-brand-bg transition-colors">
                <span className="text-xs font-body text-brand-text">{r.period}</span>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-body text-brand-muted">
                    {r.ghost_count > 0 && <span className="text-[#ff4d6d] mr-2">{r.ghost_count} ghosts</span>}
                    {r.missing_count > 0 && <span className="text-[#f5a623]">{r.missing_count} missing</span>}
                  </span>
                  <span className={`text-[10px] font-body px-2 py-0.5 rounded-sm ${STATUS_STYLE[r.status] ?? STATUS_STYLE.pending}`}>
                    {r.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
        {historyLoaded && history.length === 0 && (
          <p className="text-xs font-body text-brand-muted">No runs yet.</p>
        )}
      </div>
    </motion.div>
  )
}
