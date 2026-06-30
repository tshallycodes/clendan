'use client'

import { useState, useEffect } from 'react'
import { useUser } from '@clerk/nextjs'

interface Props {
  onNext: () => void
}

const INPUT = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-body text-brand-text placeholder:text-brand-muted outline-none transition-colors'
const LABEL = 'text-[10px] font-body text-brand-muted uppercase tracking-widest'

export function StepName({ onNext }: Props) {
  const { user, isLoaded } = useUser()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Pre-fill from Clerk profile (populated for SSO users automatically)
  useEffect(() => {
    if (!isLoaded || !user) return
    if (user.firstName) setFirstName(user.firstName)
    if (user.lastName) setLastName(user.lastName)
  }, [isLoaded, user])

  const email = user?.primaryEmailAddress?.emailAddress ?? ''

  async function handleSubmit() {
    if (!firstName.trim()) return
    setLoading(true)
    setError(null)
    try {
      await user?.update({ firstName: firstName.trim(), lastName: lastName.trim() })
      onNext()
    } catch {
      setError('Could not save your name. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="font-heading font-bold text-[28px] text-brand-text">Welcome to Clendan</h1>
        <p className="text-xs font-body text-brand-muted">Let's start with your details.</p>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className={LABEL}>
              First name <span className="text-brand-danger">*</span>
            </label>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="Jane"
              autoComplete="given-name"
              className={INPUT}
            />
          </div>
          <div className="space-y-1.5">
            <label className={LABEL}>Last name</label>
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              placeholder="Smith"
              autoComplete="family-name"
              className={INPUT}
            />
          </div>
        </div>

        {email && (
          <div className="space-y-1.5">
            <label className={LABEL}>Email</label>
            <div className="flex items-center gap-2">
              <input
                type="email"
                value={email}
                readOnly
                className={`${INPUT} opacity-50 cursor-not-allowed select-none`}
              />
              <span className="shrink-0 text-[10px] font-body text-brand-muted border border-brand-border rounded-sm px-2 py-1.5">
                verified
              </span>
            </div>
          </div>
        )}

        {error && <p className="text-xs font-body text-brand-danger">{error}</p>}

        <button
          type="button"
          disabled={!firstName.trim() || loading || !isLoaded}
          onClick={handleSubmit}
          className="w-full bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2.5 text-xs font-body font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Saving…' : 'Continue →'}
        </button>
      </div>
    </div>
  )
}
