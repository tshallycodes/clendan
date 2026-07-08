'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { AnimatePresence, motion } from 'framer-motion'
import { useToast, useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface SuggestedLine {
  account_code: string
  account_name: string
  debit_minor: number
  credit_minor: number
  description: string | null
}

export interface JournalEntrySuggestion {
  period: string
  entry_type: string
  description: string
  lines: SuggestedLine[]
  reasoning?: string | null
}

interface Props {
  suggestion: JournalEntrySuggestion | null
  onClose: () => void
  onCreated: () => void
}

function fmt(minor: number, currency: string): string {
  const info = CURRENCY_MAP[currency]
  const decimals = info?.decimals ?? 2
  const divisor = Math.pow(10, decimals)
  return (minor / divisor).toLocaleString('en-GB', { style: 'currency', currency: currency || 'GBP' })
}

export function CreateJournalEntryModal({ suggestion, onClose, onCreated }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const { currency } = useCurrency()
  const [submitting, setSubmitting] = useState(false)

  if (!suggestion) return null

  async function handleCreate() {
    if (!suggestion) return
    setSubmitting(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/journal-entries`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `journal-modal-${Date.now()}`,
        },
        body: JSON.stringify({
          period: suggestion.period,
          entry_type: suggestion.entry_type,
          description: suggestion.description,
          lines: suggestion.lines.map(l => ({
            account_code: l.account_code,
            account_name: l.account_name,
            debit_minor: l.debit_minor,
            credit_minor: l.credit_minor,
            description: l.description ?? null,
          })),
        }),
      })
      if (!res.ok) {
        toast('Failed to create journal entry', 'error')
        return
      }
      toast('Journal entry created', 'success')
      onCreated()
    } catch {
      toast('Network error', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: 'rgba(0,0,0,0.7)' }}
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.97, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 8 }}
          transition={{ duration: 0.15 }}
          className="bg-brand-surface border border-brand-border rounded-sm w-full max-w-xl overflow-hidden"
          onClick={e => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
            <div>
              <h3 className="text-[14px] font-body font-semibold text-brand-text capitalize">
                Create {suggestion.entry_type} Entry
              </h3>
              <p className="text-[11px] font-body text-brand-muted mt-0.5">
                AI-suggested - review before creating
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none"
              aria-label="Close"
            >
              &#215;
            </button>
          </div>

          {/* Body */}
          <div className="px-5 py-4 space-y-4">
            {/* Meta */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className="text-[10px] font-body text-brand-muted uppercase tracking-widest mb-1">Period</p>
                <p className="text-[12px] font-body text-brand-text">{suggestion.period}</p>
              </div>
              <div>
                <p className="text-[10px] font-body text-brand-muted uppercase tracking-widest mb-1">Type</p>
                <p className="text-[12px] font-body text-brand-text capitalize">{suggestion.entry_type}</p>
              </div>
              <div>
                <p className="text-[10px] font-body text-brand-muted uppercase tracking-widest mb-1">Description</p>
                <p className="text-[12px] font-body text-brand-text truncate" title={suggestion.description}>
                  {suggestion.description}
                </p>
              </div>
            </div>

            {/* Lines table */}
            <div className="border border-brand-border rounded-sm overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-brand-border bg-brand-elevated">
                    {['Code', 'Account', 'Description', 'Debit', 'Credit'].map(h => (
                      <th
                        key={h}
                        className={`text-[10px] font-body text-brand-muted uppercase tracking-widest px-3 py-2 ${
                          h === 'Debit' || h === 'Credit' ? 'text-right' : 'text-left'
                        }`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {suggestion.lines.map((ln, i) => (
                    <tr key={i} className="border-b border-brand-border last:border-0">
                      <td className="px-3 py-2 text-[12px] font-body text-brand-muted">{ln.account_code}</td>
                      <td className="px-3 py-2 text-[12px] font-body text-brand-text">{ln.account_name}</td>
                      <td className="px-3 py-2 text-[12px] font-body text-brand-muted">{ln.description ?? '-'}</td>
                      <td className="px-3 py-2 text-[12px] font-body text-brand-text text-right tabular-nums">
                        {ln.debit_minor > 0 ? fmt(ln.debit_minor, currency) : '-'}
                      </td>
                      <td className="px-3 py-2 text-[12px] font-body text-brand-text text-right tabular-nums">
                        {ln.credit_minor > 0 ? fmt(ln.credit_minor, currency) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Reasoning */}
            {suggestion.reasoning && (
              <div>
                <p className="text-[10px] font-body text-brand-muted uppercase tracking-widest mb-1">Reasoning</p>
                <p className="text-[12px] font-body text-brand-secondary leading-relaxed">{suggestion.reasoning}</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-brand-border">
            <button
              type="button"
              onClick={onClose}
              className="text-[12px] font-body border border-brand-border text-brand-muted hover:text-brand-text rounded-sm px-4 py-1.5 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreate}
              disabled={submitting}
              className="text-[12px] font-body bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-1.5 transition-all disabled:opacity-40"
            >
              {submitting ? 'Creating…' : 'Create Entry'}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
