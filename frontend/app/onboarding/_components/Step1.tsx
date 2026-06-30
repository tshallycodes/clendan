'use client'

import { useState, useEffect } from 'react'
import { useAuth, useUser } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const INDUSTRIES = ['Technology', 'Finance', 'Healthcare', 'Retail', 'Manufacturing', 'Professional Services', 'Other']
const COMPANY_SIZES = ['1–10', '11–50', '51–200', '201–1000', '1000+']
const USE_CASES = ['Invoice Processing', 'Expense Management', 'Financial Reporting', 'All of the above']

interface Step1Data {
  name: string
  industry: string
  size: string
  useCase: string
}

interface Step1Props {
  onNext: () => void
}

const INPUT = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-body text-brand-text placeholder:text-brand-muted outline-none transition-colors'
const LABEL = 'text-[10px] font-body text-brand-muted uppercase tracking-widest'

export function Step1({ onNext }: Step1Props) {
  const { getToken } = useAuth()
  const { user } = useUser()
  const [data, setData] = useState<Step1Data>({ name: '', industry: INDUSTRIES[0], size: COMPANY_SIZES[0], useCase: USE_CASES[0] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) return
    async function provisionOrg() {
      try {
        const token = await getToken()
        const email = user?.primaryEmailAddress?.emailAddress ?? ''
        await fetch(`${API}/organisations`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        })
      } catch {
        // idempotent provision — ignore errors on mount
      }
    }
    provisionOrg()
  }, [getToken, user])

  async function handleSubmit() {
    if (!data.name.trim()) return
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/onboarding/organisation`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: data.name.trim(), industry: data.industry, size: data.size }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Setup failed. Please try again.')
        return
      }
      onNext()
    } catch {
      setError('Unable to connect to server.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="font-heading font-bold text-[28px] text-brand-text">Tell us about your company</h1>
        <p className="text-xs font-body text-brand-muted">We'll configure your workspace accordingly.</p>
      </div>
      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className={LABEL}>Company name <span className="text-brand-danger">*</span></label>
          <input
            type="text"
            value={data.name}
            onChange={(e) => setData((p) => ({ ...p, name: e.target.value }))}
            placeholder="Acme Corp"
            className={INPUT}
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="s1-industry" className={LABEL}>Industry</label>
          <select id="s1-industry" value={data.industry} onChange={(e) => setData((p) => ({ ...p, industry: e.target.value }))} className={INPUT}>
            {INDUSTRIES.map((v) => <option key={v}>{v}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="s1-size" className={LABEL}>Company size</label>
          <select id="s1-size" value={data.size} onChange={(e) => setData((p) => ({ ...p, size: e.target.value }))} className={INPUT}>
            {COMPANY_SIZES.map((v) => <option key={v}>{v}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="s1-usecase" className={LABEL}>Primary use case</label>
          <select id="s1-usecase" value={data.useCase} onChange={(e) => setData((p) => ({ ...p, useCase: e.target.value }))} className={INPUT}>
            {USE_CASES.map((v) => <option key={v}>{v}</option>)}
          </select>
        </div>
        {error && <p className="text-xs font-body text-brand-danger">{error}</p>}
        <button
          type="button"
          disabled={!data.name.trim() || loading}
          onClick={handleSubmit}
          className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2.5 text-xs font-body font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Setting up…' : 'Next →'}
        </button>
      </div>
    </div>
  )
}
