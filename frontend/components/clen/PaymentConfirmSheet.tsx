'use client'

import { motion } from 'framer-motion'
import { formatMinor, maskAccount, useActionConfirm, type ProposedAction } from './useActionConfirm'

// The details-verified confirmation for a money (capability="money") proposal. Nothing here moves
// funds: confirming PREPARES the payment (records intent) for the authorised human to release in
// the bank/ERP. The red banner flags a supplier bank-account change since the last payment - the
// classic mandate-fraud vector - so it is verified before anything is prepared.
export function PaymentConfirmSheet({ proposedAction }: { proposedAction: ProposedAction }) {
  const { state, message, act } = useActionConfirm(proposedAction.action_id)
  const d = proposedAction.details ?? {}
  const accountChanged = Boolean(d.account_changed)
  const pending = state === 'idle' || state === 'busy'

  const heading =
    state === 'confirmed' ? 'Payment prepared' : state === 'cancelled' ? 'Cancelled' : 'Verify payment details'

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="my-2 border border-[#ff4d6d] rounded-sm bg-brand-surface overflow-hidden"
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-brand-border bg-brand-bg">
        <span className="text-[#ff4d6d] text-xs" aria-hidden="true">⚡</span>
        <span className="text-[11px] font-body text-brand-secondary uppercase tracking-wider">{heading}</span>
        <span className="ml-auto text-[11px] font-body text-brand-muted">money · prepare</span>
      </div>

      <div className="px-3 py-2">
        {accountChanged && pending && (
          <div className="mb-2 flex items-start gap-2 rounded-sm border border-[#ff4d6d] bg-[rgba(255,77,109,0.08)] px-2 py-1.5">
            <span className="text-[#ff4d6d] text-xs leading-none mt-0.5" aria-hidden="true">!</span>
            <p className="text-[11px] font-body text-[#ff4d6d] leading-relaxed">
              Bank account changed since the last payment to this supplier. Verify it before you prepare this payment.
            </p>
          </div>
        )}

        <dl className="mb-3 divide-y divide-brand-border border border-brand-border rounded-sm">
          <DetailRow label="Payee" value={d.payee || '—'} />
          <DetailRow label="Account" value={maskAccount(d.account_identifier)} mono />
          <DetailRow label="Amount" value={formatMinor(d.amount_minor, d.currency)} strong />
        </dl>

        {pending ? (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={state === 'busy'}
              onClick={() => act('confirm')}
              className="flex-1 h-7 text-[12px] font-body font-medium rounded-sm bg-brand-green text-black hover:bg-[#00a844] transition-colors active:scale-[0.97] disabled:opacity-50"
            >
              {state === 'busy' ? '…' : 'Confirm & prepare'}
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
          <p className="text-[11px] font-body text-brand-green">
            ✓ Prepared — release it in your bank/ERP. Clendan never moves the money.
          </p>
        ) : state === 'cancelled' ? (
          <p className="text-[11px] font-body text-brand-muted">Cancelled — nothing was prepared.</p>
        ) : (
          <p className="text-[11px] font-body text-[#ff4d6d]">{message}</p>
        )}
      </div>
    </motion.div>
  )
}

function DetailRow({ label, value, mono, strong }: { label: string; value: string; mono?: boolean; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 px-2.5 py-1.5">
      <dt className="text-[10px] font-body uppercase tracking-wider text-brand-muted shrink-0">{label}</dt>
      <dd
        className={`text-[12px] font-body text-right truncate ${strong ? 'font-medium text-brand-text' : 'text-brand-secondary'} ${
          mono ? 'tabular-nums' : ''
        }`}
      >
        {value}
      </dd>
    </div>
  )
}
