'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Step3Props {
  onNext: () => void
  onSkip: () => void
}

export function Step3({ onNext, onSkip }: Step3Props) {
  const { getToken } = useAuth()
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleQuickBooks() {
    setConnecting(true)
    setError(null)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/integrations/quickbooks/connect`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        setError((json as { error?: string }).error ?? 'Connection failed. Try again.')
        return
      }
      const json = await res.json() as { data?: { auth_url?: string } }
      const authUrl = json.data?.auth_url
      if (authUrl) {
        window.location.href = authUrl
      } else {
        setError('No auth URL returned. Contact support.')
      }
    } catch {
      setError('Unable to connect to server.')
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="font-heading font-bold text-[28px] text-brand-text">Connect your accounting software</h1>
        <p className="text-xs font-body text-brand-muted">Link a system to enable automatic financial sync.</p>
      </div>
      <div className="space-y-3">
        <div className="bg-brand-surface border border-brand-border rounded-sm p-5 space-y-3">
          <div>
            <p className="text-sm font-body text-brand-text font-medium">QuickBooks</p>
            <p className="text-[10px] font-body text-brand-muted mt-0.5">
              Sync invoices, bills, payments, and chart of accounts automatically.
            </p>
          </div>
          <button
            type="button"
            onClick={handleQuickBooks}
            disabled={connecting}
            className="border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-4 py-2 text-xs font-body transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {connecting ? 'Connecting…' : 'Connect QuickBooks'}
          </button>
        </div>
        <div className="relative bg-brand-surface border border-brand-border rounded-sm p-5 opacity-50">
          <div>
            <p className="text-sm font-body text-brand-text font-medium">Plaid</p>
            <p className="text-[10px] font-body text-brand-muted mt-0.5">
              Bank account connections and transaction data.
            </p>
          </div>
          <div className="mt-3">
            <span
              title="Set up during account creation"
              className="inline-flex cursor-not-allowed border border-brand-border text-brand-muted rounded-sm px-4 py-2 text-xs font-body"
            >
              Connect Plaid
            </span>
          </div>
        </div>
      </div>
      {error && <p className="text-xs font-body text-brand-danger">{error}</p>}
      <button
        type="button"
        onClick={onSkip}
        className="w-full text-xs font-body text-brand-muted hover:text-brand-text transition-colors py-1"
      >
        Skip for now — I'll connect later
      </button>
    </div>
  )
}
