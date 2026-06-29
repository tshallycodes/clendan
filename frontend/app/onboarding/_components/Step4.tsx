'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type AutonomyLevel = 'auto' | 'approve'

interface AutonomyOption {
  level: AutonomyLevel
  label: string
  desc: string
}

const OPTIONS: AutonomyOption[] = [
  { level: 'auto', label: 'Auto', desc: 'Execute automatically. No human approval needed.' },
  { level: 'approve', label: 'Approve', desc: 'Requires human approval before execution.' },
]

interface Step4Props {
  onBack: () => void
}

export function Step4({ onBack }: Step4Props) {
  const router = useRouter()
  const { getToken } = useAuth()
  const [autonomy, setAutonomy] = useState<AutonomyLevel>('approve')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleDeploy() {
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const toolRes = await fetch(`${API}/tools`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'invoice_processing', autonomy_level: autonomy }),
      })
      if (!toolRes.ok) {
        const json = await toolRes.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Tool deploy failed.')
        return
      }
      const completeRes = await fetch(`${API}/onboarding/complete`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      if (!completeRes.ok) {
        const json = await completeRes.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Could not complete onboarding.')
        return
      }
      router.push('/dashboard')
    } catch {
      setError('Unable to connect to server.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="font-heading font-bold text-[28px] text-brand-text">Deploy your first tool</h1>
        <p className="text-xs font-mono text-brand-muted">Invoice Processing Tool is ready to deploy.</p>
      </div>
      <div className="bg-brand-surface border-l-[3px] border-l-brand-green border border-brand-border rounded-sm p-4">
        <p className="text-sm font-mono text-brand-text font-medium">Invoice Processing Tool</p>
        <p className="text-[10px] font-mono text-brand-muted mt-0.5">
          Reads, classifies, and routes incoming invoices.
        </p>
      </div>
      <div className="space-y-2">
        {OPTIONS.map((opt) => (
          <button
            key={opt.level}
            type="button"
            onClick={() => setAutonomy(opt.level)}
            className={[
              'w-full text-left bg-brand-surface border rounded-sm p-4 transition-colors',
              autonomy === opt.level ? 'border-brand-green' : 'border-brand-border hover:border-brand-secondary',
            ].join(' ')}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-mono text-brand-text font-medium">{opt.label}</p>
                <p className="text-[10px] font-mono text-brand-muted mt-0.5">{opt.desc}</p>
              </div>
              {autonomy === opt.level && <span className="text-brand-green text-xs font-mono">✓</span>}
            </div>
          </button>
        ))}
      </div>
      {error && <p className="text-xs font-mono text-brand-danger">{error}</p>}
      <button
        type="button"
        onClick={handleDeploy}
        disabled={loading}
        className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2.5 text-xs font-mono font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Deploying…' : 'Deploy Tool →'}
      </button>
    </div>
  )
}
