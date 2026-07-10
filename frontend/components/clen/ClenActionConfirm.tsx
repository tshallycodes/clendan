'use client'

import { motion } from 'framer-motion'
import { PaymentConfirmSheet } from './PaymentConfirmSheet'
import { useActionConfirm, type ProposedAction } from './useActionConfirm'

// Re-exported so existing importers (ClenMessage) keep their import path.
export type { ProposedAction } from './useActionConfirm'

// The confirm gate for anything the agent proposes. The agent never acts on its own - it proposes
// an action and this is where the user releases or declines it. Money actions (capability="money")
// render a details-verified sheet instead; nothing here moves funds - it prepares.
export function ClenActionConfirm({ proposedAction }: { proposedAction: ProposedAction }) {
  if (proposedAction.capability === 'money') {
    return <PaymentConfirmSheet proposedAction={proposedAction} />
  }
  return <StandardActionConfirm proposedAction={proposedAction} />
}

function StandardActionConfirm({ proposedAction }: { proposedAction: ProposedAction }) {
  const { state, message, act } = useActionConfirm(proposedAction.action_id)
  const heading =
    state === 'confirmed' ? 'Confirmed' : state === 'cancelled' ? 'Cancelled' : 'Needs your confirmation'

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="my-2 border border-brand-border rounded-sm bg-brand-surface overflow-hidden"
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-brand-border bg-brand-bg">
        <span className="text-brand-warning text-xs" aria-hidden="true">⚡</span>
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
