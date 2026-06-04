'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export default function OnboardingPage() {
  const router = useRouter()
  const { getToken } = useAuth()

  const [companyName, setCompanyName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!companyName.trim()) return

    setLoading(true)
    setError(null)

    try {
      const token = await getToken()
      const res = await fetch(`${API_BASE}/v1/onboarding`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tenant_name: companyName.trim() }),
      })

      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Something went wrong. Please try again.')
        return
      }

      router.push('/dashboard')
    } catch {
      setError('Unable to connect to server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-8">
        <div className="flex flex-col items-center gap-3">
          <span className="w-10 h-10 rounded-sm border border-brand-green flex items-center justify-center font-heading font-bold text-brand-green text-lg">
            C
          </span>
          <span className="font-heading font-bold text-brand-text text-xs tracking-[0.15em] uppercase">
            Clendan
          </span>
        </div>

        <div className="text-center space-y-2">
          <h1 className="font-heading font-bold text-[28px] text-brand-text leading-tight">
            Create your workspace
          </h1>
          <p className="text-xs font-mono text-brand-muted">
            Set up your organisation to begin deploying AI financial workers.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">
              Company name
            </label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Acme Corp"
              required
              disabled={loading}
              className="w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2.5 text-xs font-mono text-brand-text placeholder:text-brand-muted outline-none transition-colors disabled:opacity-50"
            />
          </div>

          {error && (
            <p className="text-xs font-mono text-brand-danger">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !companyName.trim()}
            className="w-full bg-brand-green text-black hover:bg-[#00a844] rounded-sm px-4 py-2.5 text-xs font-mono font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Creating workspace…' : 'Create workspace →'}
          </button>
        </form>
      </div>
    </div>
  )
}
