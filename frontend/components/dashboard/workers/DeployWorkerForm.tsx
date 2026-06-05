'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const WORKER_TYPES = [
  { value: 'invoice_processing',  label: 'Invoice Processing' },
  { value: 'ai_accountant',       label: 'AI Accountant' },
  { value: 'receipt_processing',  label: 'Receipt Processing' },
  { value: 'reconciliation',      label: 'Reconciliation' },
  { value: 'expense_control',     label: 'Expense Control' },
  { value: 'collections',         label: 'Collections' },
  { value: 'fraud_detection',     label: 'Fraud Detection' },
  { value: 'treasury',            label: 'Treasury' },
  { value: 'revenue_recognition', label: 'Revenue Recognition' },
  { value: 'credit_underwriting', label: 'Credit Underwriting' },
  { value: 'compliance',          label: 'Compliance' },
] as const

const AUTONOMY_LEVELS = [
  { value: 'auto',    label: 'Auto',    description: 'Executes without human approval' },
  { value: 'approve', label: 'Approve', description: 'Requires human approval above threshold' },
  { value: 'suggest', label: 'Suggest', description: 'Suggests actions, never executes' },
] as const

type WorkerType = typeof WORKER_TYPES[number]['value']
type AutonomyLevel = typeof AUTONOMY_LEVELS[number]['value']

interface DeployWorkerFormProps {
  defaultWorkerType?: string
  onDeployed?: () => void
}

export function DeployWorkerForm({ defaultWorkerType, onDeployed }: DeployWorkerFormProps) {
  const { getToken } = useAuth()

  const initialType = (WORKER_TYPES.find(t => t.value === defaultWorkerType)?.value ?? 'invoice_processing') as WorkerType
  const [workerType, setWorkerType] = useState<WorkerType>(initialType)
  const [autonomyLevel, setAutonomyLevel] = useState<AutonomyLevel>('approve')
  const [autoThreshold, setAutoThreshold] = useState(50000)
  const [approveThreshold, setApproveThreshold] = useState(500000)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const token = await getToken()
      const res = await fetch(`${API_BASE}/v1/workers`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: workerType,
          autonomy_level: autonomyLevel,
          config: {
            policy: {
              auto_threshold: autoThreshold,
              approve_threshold: approveThreshold,
              allowed_currencies: ['GBP', 'USD'],
            },
          },
        }),
      })

      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Failed to deploy worker.')
        return
      }

      if (onDeployed) onDeployed()
    } catch {
      setError('Unable to connect to server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const selectClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text outline-none transition-colors'
  const inputClass  = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text outline-none transition-colors'
  const labelClass  = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <label className={labelClass}>Worker Type</label>
        <select value={workerType} onChange={(e) => setWorkerType(e.target.value as WorkerType)} className={selectClass}>
          {WORKER_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label className={labelClass}>Autonomy Level</label>
        <select value={autonomyLevel} onChange={(e) => setAutonomyLevel(e.target.value as AutonomyLevel)} className={selectClass}>
          {AUTONOMY_LEVELS.map((a) => (
            <option key={a.value} value={a.value}>{a.label} — {a.description}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className={labelClass}>Auto Threshold (pence)</label>
          <input type="number" min={0} value={autoThreshold} onChange={(e) => setAutoThreshold(Number(e.target.value))} className={inputClass} />
          <p className="text-[10px] font-mono text-brand-muted">£{(autoThreshold / 100).toFixed(2)}</p>
        </div>
        <div className="space-y-1.5">
          <label className={labelClass}>Approve Threshold (pence)</label>
          <input type="number" min={0} value={approveThreshold} onChange={(e) => setApproveThreshold(Number(e.target.value))} className={inputClass} />
          <p className="text-[10px] font-mono text-brand-muted">£{(approveThreshold / 100).toFixed(2)}</p>
        </div>
      </div>

      {error && <p className="text-xs font-mono text-brand-danger">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="bg-brand-green text-black hover:bg-[#00a844] rounded-sm px-4 py-2 text-xs font-mono transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Deploying…' : 'Deploy Worker'}
      </button>
    </form>
  )
}
