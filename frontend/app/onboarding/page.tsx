'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth, useClerk } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type AutonomyLevel = 'auto' | 'approve' | 'suggest'

interface StepOneData {
  companyName: string
  industry: string
  companySize: string
  useCase: string
}

function ProgressBar({ step }: { step: number }) {
  return (
    <div className="flex items-center gap-2 mb-10">
      {[1, 2, 3, 4].map((n, i) => (
        <div key={n} className="flex items-center gap-2">
          <div className={[
            'w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-medium border transition-colors',
            n < step ? 'bg-transparent border-brand-green text-brand-green' :
            n === step ? 'bg-brand-green border-brand-green text-black' :
            'bg-transparent border-brand-border text-brand-muted',
          ].join(' ')}>
            {n < step ? '✓' : n}
          </div>
          {i < 3 && <div className={`h-px w-8 ${n < step ? 'bg-brand-green' : 'bg-brand-border'}`} />}
        </div>
      ))}
      <span className="ml-2 text-[10px] font-mono text-brand-muted">Step {step} of 4</span>
    </div>
  )
}

function OnboardingInner() {
  const router = useRouter()
  const params = useSearchParams()
  const { getToken } = useAuth()
  const { signOut } = useClerk()
  const step = Number(params.get('step') ?? '1')

  const [stepOne, setStepOne] = useState<StepOneData>({ companyName: '', industry: 'SaaS', companySize: '1-10', useCase: 'Invoice Processing' })
  const [autonomy, setAutonomy] = useState<AutonomyLevel>('approve')
  const [threshold, setThreshold] = useState(50000)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2.5 text-xs font-mono text-brand-text outline-none transition-colors'
  const inputClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2.5 text-xs font-mono text-brand-text placeholder:text-brand-muted outline-none transition-colors'
  const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

  async function handleStepOne() {
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/onboarding`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_name: stepOne.companyName.trim() }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Setup failed. Please try again.')
        return
      }
      router.push('/onboarding?step=2')
    } catch {
      setError('Unable to connect to server. Check the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  async function handleDeploy() {
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/workers`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'invoice_processing',
          autonomy_level: autonomy,
          config: { policy: { auto_threshold: threshold, approve_threshold: 500000 } },
        }),
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Worker deploy failed.')
        return
      }
      router.push('/onboarding?step=4')
    } catch {
      setError('Unable to connect to server. Check the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col items-center justify-center p-6">
      {/* Top nav */}
      <div className="fixed top-0 left-0 right-0 flex items-center justify-between px-6 py-4">
        {step > 1 && step < 4 ? (
          <button
            type="button"
            onClick={() => router.push(`/onboarding?step=${step - 1}`)}
            className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors"
          >
            ← Back
          </button>
        ) : (
          <div />
        )}
        {step < 4 && (
          <button
            type="button"
            onClick={() => signOut({ redirectUrl: '/sign-in' })}
            className="text-xs font-mono text-brand-muted hover:text-brand-text transition-colors"
          >
            Sign out
          </button>
        )}
      </div>

      <div className="w-full max-w-md space-y-0">
        <div className="flex flex-col items-center gap-3 mb-10">
          <span className="w-10 h-10 rounded-sm border border-brand-green flex items-center justify-center font-heading font-bold text-brand-green text-lg">C</span>
          <span className="font-heading font-bold text-brand-text text-xs tracking-[0.15em] uppercase">Clendan</span>
        </div>

        <ProgressBar step={step} />

        {step === 1 && (
          <div className="space-y-6">
            <div className="text-center space-y-1">
              <h1 className="font-heading font-bold text-[28px] text-brand-text">Tell us about your company</h1>
              <p className="text-xs font-mono text-brand-muted">We'll configure your workspace accordingly.</p>
            </div>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className={labelClass}>Company name <span className="text-[#ff4d6d]">*</span></label>
                <input type="text" value={stepOne.companyName} onChange={(e) => setStepOne((p) => ({ ...p, companyName: e.target.value }))} placeholder="Acme Corp" className={inputClass} />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="industry" className={labelClass}>Industry</label>
                <select id="industry" value={stepOne.industry} onChange={(e) => setStepOne((p) => ({ ...p, industry: e.target.value }))} className={selectClass}>
                  {['SaaS', 'Fintech', 'E-commerce', 'Professional Services', 'Other'].map((v) => <option key={v}>{v}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="company-size" className={labelClass}>Company size</label>
                <select id="company-size" value={stepOne.companySize} onChange={(e) => setStepOne((p) => ({ ...p, companySize: e.target.value }))} className={selectClass}>
                  {['1-10', '11-50', '51-200', '200+'].map((v) => <option key={v}>{v}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="use-case" className={labelClass}>Primary use case</label>
                <select id="use-case" value={stepOne.useCase} onChange={(e) => setStepOne((p) => ({ ...p, useCase: e.target.value }))} className={selectClass}>
                  {['Invoice Processing', 'Reconciliation', 'Expense Management', 'Other'].map((v) => <option key={v}>{v}</option>)}
                </select>
              </div>
              {error && <p className="text-xs font-mono text-[#ff4d6d]">{error}</p>}
              <button
                type="button"
                disabled={!stepOne.companyName.trim() || loading}
                onClick={handleStepOne}
                className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2.5 text-xs font-mono font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Setting up…' : 'Next →'}
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6">
            <div className="text-center space-y-1">
              <h1 className="font-heading font-bold text-[28px] text-brand-text">Connect your accounting software</h1>
              <p className="text-xs font-mono text-brand-muted">Link a system to get started with automatic sync.</p>
            </div>
            <div className="space-y-3">
              <a href="/dashboard/integrations" className="block bg-brand-surface border border-brand-green rounded-sm p-5 hover:bg-brand-elevated transition-colors">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-mono text-brand-text font-medium">QuickBooks</p>
                    <p className="text-[10px] font-mono text-brand-muted mt-0.5">Connect via OAuth in the integrations page</p>
                  </div>
                  <span className="text-xs font-mono text-brand-green">Connect in Dashboard →</span>
                </div>
              </a>
              <div className="bg-brand-surface border border-brand-border rounded-sm p-5 opacity-50 cursor-not-allowed">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-mono text-brand-text font-medium">Xero</p>
                    <p className="text-[10px] font-mono text-brand-muted mt-0.5">Bills, invoices, payments</p>
                  </div>
                  <span className="text-[10px] font-mono text-brand-muted border border-brand-border rounded-sm px-2 py-0.5">Coming Soon</span>
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => router.push('/onboarding?step=3')}
              className="w-full text-xs font-mono text-brand-muted hover:text-brand-text transition-colors py-2"
            >
              Skip for now — I'll connect later
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            <div className="text-center space-y-1">
              <h1 className="font-heading font-bold text-[28px] text-brand-text">Deploy your first worker</h1>
              <p className="text-xs font-mono text-brand-muted">Configure your Invoice Processing Worker.</p>
            </div>
            <div className="space-y-3">
              {([
                { level: 'auto' as AutonomyLevel, label: 'Auto', desc: 'Processes under threshold without approval' },
                { level: 'approve' as AutonomyLevel, label: 'Approve', desc: 'Always asks before acting' },
                { level: 'suggest' as AutonomyLevel, label: 'Suggest', desc: 'Recommends actions, you execute manually' },
              ]).map((opt) => (
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
                    {autonomy === opt.level && <span className="text-brand-green text-sm">✓</span>}
                  </div>
                </button>
              ))}
            </div>
            {autonomy === 'auto' && (
              <div className="space-y-1.5">
                <label htmlFor="auto-threshold" className={labelClass}>Auto-approve invoices under £</label>
                <input
                  id="auto-threshold"
                  type="number"
                  min={0}
                  placeholder="500.00"
                  value={(threshold / 100).toFixed(2)}
                  onChange={(e) => setThreshold(Math.round(parseFloat(e.target.value) * 100))}
                  className={inputClass}
                />
                <p className="text-[10px] font-mono text-brand-muted">Stored as {threshold} pence</p>
              </div>
            )}
            {error && <p className="text-xs font-mono text-[#ff4d6d]">{error}</p>}
            <button
              type="button"
              onClick={handleDeploy}
              disabled={loading}
              className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2.5 text-xs font-mono font-medium transition-all disabled:opacity-50"
            >
              {loading ? 'Deploying…' : 'Deploy Worker'}
            </button>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-8 text-center">
            <div className="space-y-2">
              <h1 className="font-heading font-extrabold text-[48px] text-brand-text leading-none">You're ready.</h1>
              <p className="text-sm font-mono text-brand-secondary">Your Invoice Processing Worker is live.</p>
            </div>
            <div className="space-y-3 text-left">
              {['Worker deployed', 'Policy configured', 'Audit trail active'].map((item) => (
                <div key={item} className="flex items-center gap-3">
                  <span className="text-brand-green text-base">✓</span>
                  <span className="text-xs font-mono text-brand-text">{item}</span>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => router.push('/dashboard')}
              className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-3 text-sm font-mono font-medium transition-all"
            >
              Go to Dashboard →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function OnboardingPage() {
  return (
    <Suspense>
      <OnboardingInner />
    </Suspense>
  )
}
