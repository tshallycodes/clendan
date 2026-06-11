'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { WorkerConfigFields, getDefaultConfig } from './WorkerConfigFields'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const WORKER_TYPES = [
  { value: 'invoice_processing',  label: 'Invoice Processing'  },
  { value: 'ai_accountant',       label: 'AI Accountant'       },
  { value: 'receipt_processing',  label: 'Receipt Processing'  },
  { value: 'reconciliation',      label: 'Reconciliation'      },
  { value: 'expense_control',     label: 'Expense Control'     },
  { value: 'collections',         label: 'Collections'         },
  { value: 'fraud_detection',     label: 'Fraud Detection'     },
  { value: 'treasury',            label: 'Treasury'            },
  { value: 'revenue_recognition', label: 'Revenue Recognition' },
  { value: 'credit_underwriting', label: 'Credit Underwriting' },
  { value: 'compliance',          label: 'Compliance'          },
] as const

const AUTONOMY_LEVELS = [
  { value: 'auto',    label: 'Auto',    description: 'Executes without human approval'         },
  { value: 'approve', label: 'Approve', description: 'Requires human approval above threshold' },
  { value: 'suggest', label: 'Suggest', description: 'Suggests actions, never executes'        },
] as const

type WorkerType = typeof WORKER_TYPES[number]['value']
type AutonomyLevel = typeof AUTONOMY_LEVELS[number]['value']

interface DeployWorkerFormProps {
  onDeployed?: () => void
}

export function DeployWorkerForm({ onDeployed }: DeployWorkerFormProps) {
  const { getToken } = useAuth()
  const [workerType, setWorkerType] = useState<WorkerType>('invoice_processing')
  const [autonomyLevel, setAutonomyLevel] = useState<AutonomyLevel>('approve')
  const [config, setConfig] = useState<Record<string, unknown>>(getDefaultConfig('invoice_processing'))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleWorkerTypeChange(type: WorkerType) {
    setWorkerType(type)
    setConfig(getDefaultConfig(type))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API_BASE}/v1/tools`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: workerType, autonomy_level: autonomyLevel, config }),
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
  const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <label className={labelClass}>Worker Type</label>
        <select title="Worker type" value={workerType} onChange={e => handleWorkerTypeChange(e.target.value as WorkerType)} className={selectClass}>
          {WORKER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>

      <div className="space-y-1.5">
        <label className={labelClass}>Autonomy Level</label>
        <select title="Autonomy level" value={autonomyLevel} onChange={e => setAutonomyLevel(e.target.value as AutonomyLevel)} className={selectClass}>
          {AUTONOMY_LEVELS.map(a => <option key={a.value} value={a.value}>{a.label} — {a.description}</option>)}
        </select>
      </div>

      <WorkerConfigFields
        workerType={workerType}
        config={config}
        onChange={(key, value) => setConfig(prev => ({ ...prev, [key]: value }))}
      />

      {error && <p className="text-xs font-mono text-brand-danger">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-brand-green text-black hover:bg-[#00a844] rounded-sm px-4 py-2 text-xs font-mono transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Deploying…' : 'Deploy Worker'}
      </button>
    </form>
  )
}
