'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ProposedAction {
  action_id: string
  kind?: string
  capability?: string
  preview: string
  requires_confirmation?: boolean
  expires_at?: string
}

type State = 'idle' | 'busy' | 'confirmed' | 'cancelled' | 'error'

// The confirm gate for anything the agent proposes. The agent never acts on its own - it
// proposes an action and this card is where the user releases or declines it. Money actions
// (capability="money") render with a danger accent; nothing here moves funds - it prepares.
export function ClenActionConfirm({ proposedAction }: { proposedAction: ProposedAction }) {
  const { getToken } = useAuth()
  const [state, setState] = useState<State>('idle')
  const [message, setMessage] = useState('')

  async function act(kind: 'confirm' | 'cancel') {
    setState('busy')
    try {
      const token = await getToken()
      const res = await fetch(`${API}/clen/actions/${proposedAction.action_id}/${kind}`, {
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

  const isMoney = proposedAction.capability === 'money'
  const heading =
    state === 'confirmed' ? 'Confirmed' : state === 'cancelled' ? 'Cancelled' : 'Needs your confirmation'

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={`my-2 border rounded-sm bg-brand-surface overflow-hidden ${
        isMoney ? 'border-[#ff4d6d]' : 'border-brand-border'
      }`}
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-brand-border bg-brand-bg">
        <span className={isMoney ? 'text-[#ff4d6d] text-xs' : 'text-brand-warning text-xs'}>⚡</span>
        <span className="text-[11px] font-body text-brand-secondary uppercase tracking-wider">{heading}</span>
        {proposedAction.capability && (
          <span className="ml-auto text-[11px] font-body text-brand-muted">{proposedAction.capability}</span>
        )}
      </div>

      <div className="px-3 py-2">
        <p className="text-xs font-body text-brand-text mb-3">{proposedAction.preview}</p>

        {state === 'idle' || state === 'busy' ? (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={state === 'busy'}
              onClick={() => act('confirm')}
              className="flex-1 h-7 text-[12px] font-body font-medium rounded-sm bg-brand-green text-black hover:bg-[#00a844] transition-colors active:scale-[0.97] disabled:opacity-50"
            >
              {state === 'busy' ? '…' : 'Confirm & run'}
            </button>
            <button
              type="button"
              disabled={state === 'busy'}
              onClick={() => act('cancel')}
              className="flex-1 h-7 text-[12px] font-body text-brand-secondary border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        ) : state === 'confirmed' ? (
          <p className="text-[11px] font-body text-brand-green">✓ Running now — track it in Activity.</p>
        ) : state === 'cancelled' ? (
          <p className="text-[11px] font-body text-brand-muted">Cancelled — nothing ran.</p>
        ) : (
          <p className="text-[11px] font-body text-[#ff4d6d]">{message}</p>
        )}
      </div>
    </motion.div>
  )
}
