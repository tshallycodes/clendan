'use client'

import { useRef, useState, useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { cn } from '@/lib/utils'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export interface Transaction {
  id: string
  amount_minor: number
  currency: string
  merchant_name: string | null
  description: string | null
  date: string
  ai_category: string | null
  plaid_category: string | null
  status: string
  matched_invoice_id: string | null
}

const CATEGORIES = [
  'advertising', 'bank_fees', 'consulting', 'equipment', 'insurance',
  'legal', 'meals', 'office_supplies', 'payroll', 'rent', 'software',
  'tax', 'travel', 'utilities', 'other',
]

const STATUS_STYLES: Record<string, string> = {
  matched: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border-[rgba(0,200,83,0.2)]',
  categorised: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border-[rgba(0,168,204,0.2)]',
  pending: 'bg-transparent text-brand-muted border-brand-border',
  blocked: 'bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border-[rgba(255,77,109,0.2)]',
}

function formatAmount(minor: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency, maximumFractionDigits: 2 }).format(minor / 100)
  } catch {
    return `${(minor / 100).toFixed(2)} ${currency}`
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
}

interface Props {
  transaction: Transaction
  onCategoryUpdate: (id: string, category: string) => void
}

export function TransactionRow({ transaction: t, onCategoryUpdate }: Props) {
  const { getToken } = useAuth()
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const ref = useRef<HTMLTableCellElement>(null)

  useEffect(() => {
    if (!open) return
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  async function selectCategory(category: string) {
    setOpen(false)
    setSaving(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(`${API_BASE}/v1/integrations/plaid/transactions/${t.id}/category`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ category }),
      })
      if (res.ok) onCategoryUpdate(t.id, category)
    } finally {
      setSaving(false)
    }
  }

  const statusStyle = STATUS_STYLES[t.status] ?? STATUS_STYLES.pending
  const category = t.ai_category ?? t.plaid_category

  return (
    <tr className="border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors">
      <td className="px-5 py-3 text-xs font-mono text-brand-muted whitespace-nowrap">{formatDate(t.date)}</td>
      <td className="px-5 py-3 text-xs font-mono text-brand-text max-w-[180px] truncate">
        {t.merchant_name ?? t.description ?? '—'}
      </td>
      <td className="px-5 py-3 text-xs font-mono text-brand-text whitespace-nowrap font-medium">
        {formatAmount(t.amount_minor, t.currency)}
      </td>
      <td ref={ref} className="px-5 py-3 relative">
        <button
          onClick={() => setOpen(v => !v)}
          disabled={saving}
          className="text-[10px] font-mono px-2 py-1 rounded-sm border transition-all bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border-[rgba(0,168,204,0.2)] hover:border-[rgba(0,168,204,0.4)] disabled:opacity-50"
        >
          {saving ? '…' : (category ?? 'uncategorised')}
        </button>
        {open && (
          <div className="absolute left-4 top-full mt-1 z-30 w-48 bg-brand-elevated border border-brand-border rounded-sm shadow-lg overflow-hidden">
            {CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => selectCategory(cat)}
                className={cn(
                  'w-full text-left text-[10px] font-mono px-3 py-2 transition-colors',
                  cat === category
                    ? 'text-[#00a8cc] bg-[rgba(0,168,204,0.08)]'
                    : 'text-brand-secondary hover:text-brand-text hover:bg-brand-surface',
                )}
              >
                {cat}
              </button>
            ))}
          </div>
        )}
      </td>
      <td className="px-5 py-3 text-xs font-mono text-brand-muted">
        {t.matched_invoice_id ? <span className="text-[#00C853] text-[10px]">matched</span> : '—'}
      </td>
      <td className="px-5 py-3">
        <span className={cn('text-[10px] font-mono px-2 py-1 rounded-sm border', statusStyle)}>
          {t.status}
        </span>
      </td>
    </tr>
  )
}
