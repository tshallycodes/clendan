'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Money proposals (capability="money") carry these verified details so the confirm sheet can
// show payee / masked account / amount and flag a supplier bank-account change. Nothing here
// moves funds - confirming PREPARES the payment for a human to release in the bank/ERP.
export interface MoneyDetails {
  payee?: string | null
  account_identifier?: string | null
  amount_minor?: number | null
  currency?: string | null
  account_changed?: boolean
}

export interface ProposedAction {
  action_id: string
  kind?: string
  capability?: string
  preview: string
  requires_confirmation?: boolean
  expires_at?: string
  details?: MoneyDetails
}

export type ConfirmState = 'idle' | 'busy' | 'confirmed' | 'cancelled' | 'error'

// Shared confirm/cancel gate. Both the plain action card and the money confirm sheet hit the same
// governed endpoints (/clen/actions/{id}/confirm|cancel); the backend prepares, never disburses.
export function useActionConfirm(actionId: string) {
  const { getToken } = useAuth()
  const [state, setState] = useState<ConfirmState>('idle')
  const [message, setMessage] = useState('')

  async function act(kind: 'confirm' | 'cancel') {
    setState('busy')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/clen/actions/${actionId}/${kind}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      const j = (await res.json().catch(() => ({}))) as { detail?: string; error?: string }
      if (!res.ok) {
        setState('error')
        setMessage(j.detail ?? j.error ?? 'Could not complete the action')
        return
      }
      setState(kind === 'confirm' ? 'confirmed' : 'cancelled')
    } catch {
      setState('error')
      setMessage('Connection failed - please try again')
    }
  }

  return { state, message, act }
}

// Show only the last 4 characters of a bank account identifier - never the full number.
export function maskAccount(value?: string | null): string {
  const raw = (value ?? '').replace(/\s+/g, '')
  if (!raw) return 'not on file'
  return `•••• ${raw.slice(-4)}`
}

// Integer minor units -> display string, e.g. (12345, 'GBP') -> 'GBP 123.45'. Amounts stay in
// minor units end to end; this is the only place they become a decimal, for display.
export function formatMinor(amountMinor?: number | null, currency?: string | null): string {
  const value = Math.trunc(amountMinor ?? 0)
  const major = (Math.abs(value) / 100).toFixed(2)
  const sign = value < 0 ? '-' : ''
  return `${sign}${currency || 'GBP'} ${major}`
}
