'use client'

import { useRef, useState, useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { cn } from '@/lib/utils'
import { useCurrency, useToast } from '@/components/Providers'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Transaction {
  id: string
  source: string
  amount_minor: number
  currency: string
  merchant_name: string | null
  description: string | null
  date: string
  ai_category: string | null
  plaid_category: string | null
  status: string
  matched_invoice_id: string | null
  account_id: string
  account_name: string | null
  account_subtype: string | null
  institution_name: string | null
}


const SOURCE_LABELS: Record<string, string> = {
  truelayer: 'TrueLayer',
  plaid: 'Plaid',
  mono: 'Mono',
}

const STATUS_STYLES: Record<string, string> = {
  matched:     'bg-[rgba(0,200,83,0.08)] text-[#00C853] border-[rgba(0,200,83,0.2)]',
  categorised: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border-[rgba(0,168,204,0.2)]',
  pending:     'bg-transparent text-brand-muted border-brand-border',
  blocked:     'bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border-[rgba(255,77,109,0.2)]',
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
}

function formatCategory(raw: string): string {
  return raw.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

interface Props {
  transaction: Transaction
  onCategoryUpdate: (id: string, category: string) => void
  categories: { income: string[]; expenses: string[] }
}

export function TransactionRow({ transaction: t, onCategoryUpdate, categories }: Props) {
  const { getToken } = useAuth()
  const { convert } = useCurrency()
  const { toast } = useToast()
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
      const res = await fetch(`${API_BASE}/transactions/${t.id}/category`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ category }),
      })
      if (!res.ok) { toast('Failed to save category', 'error'); return }
      onCategoryUpdate(t.id, category)
      toast('Category saved', 'success')
    } finally {
      setSaving(false)
    }
  }

  const statusStyle = STATUS_STYLES[t.status] ?? STATUS_STYLES.pending
  const activeCategory = t.ai_category ?? t.plaid_category
  const isDebit = t.amount_minor > 0

  return (
    <tr className="border-b border-brand-border last:border-0 hover:bg-brand-bg transition-colors">
      {/* Date */}
      <td className="px-5 py-3 text-xs font-body text-brand-muted whitespace-nowrap">
        {formatDate(t.date)}
      </td>

      {/* Account */}
      <td className="px-5 py-3 max-w-[140px]">
        <span className="text-xs font-body text-brand-secondary block truncate">
          {t.account_name ?? '—'}
        </span>
        <span className="text-[9px] font-body text-brand-muted uppercase tracking-wider">
          {t.account_subtype ? `${t.account_subtype} · ` : ''}{t.institution_name ?? SOURCE_LABELS[t.source] ?? t.source.toUpperCase()}
        </span>
      </td>

      {/* Merchant */}
      <td className="px-5 py-3 max-w-[200px]">
        <span className="text-xs font-body text-brand-text block truncate">
          {t.merchant_name ?? t.description ?? '—'}
        </span>
        {t.merchant_name && t.description && t.description !== t.merchant_name && (
          <span className="text-[10px] font-body text-brand-muted block truncate">{t.description}</span>
        )}
      </td>

      {/* Amount */}
      <td className="px-5 py-3 whitespace-nowrap">
        <span className={cn(
          'text-xs font-body font-medium',
          isDebit ? 'text-[#ff4d6d]' : 'text-[#00C853]',
        )}>
          {isDebit ? '−' : '+'}{convert(Math.abs(t.amount_minor), t.currency)}
        </span>
      </td>

      {/* Category */}
      <td ref={ref} className="px-5 py-3 relative">
        <div className="flex items-center gap-1.5">
          {saving ? (
            <span className="text-[10px] font-body text-brand-muted">saving…</span>
          ) : (
            <button
              onClick={() => setOpen(v => !v)}
              className={cn(
                'text-[10px] font-body px-2 py-1 rounded-sm border transition-all max-w-[140px] truncate text-left',
                activeCategory
                  ? 'bg-brand-elevated text-brand-secondary border-brand-border hover:text-brand-text hover:border-brand-border-subtle'
                  : 'bg-transparent text-brand-muted border-dashed border-brand-border hover:text-brand-secondary',
              )}
            >
              {activeCategory ? formatCategory(activeCategory) : '+ Categorise'}
            </button>
          )}
          {t.ai_category && !saving && (
            <span className="text-[9px] font-body text-brand-muted uppercase tracking-wider">AI</span>
          )}
        </div>

        {open && (
          <div className="absolute left-4 top-full mt-1 z-30 w-52 bg-brand-elevated border border-brand-border rounded-sm shadow-lg overflow-hidden max-h-72 overflow-y-auto">
            <p className="px-3 py-1.5 text-[9px] font-body text-brand-muted uppercase tracking-widest border-b border-brand-border">
              Income
            </p>
            {categories.income.map(cat => (
              <button
                key={cat}
                onClick={() => selectCategory(cat)}
                className={cn(
                  'w-full text-left text-[10px] font-body px-3 py-2 transition-colors',
                  cat === activeCategory
                    ? 'text-[#00C853] bg-brand-surface'
                    : 'text-brand-secondary hover:text-brand-text hover:bg-brand-surface',
                )}
              >
                {formatCategory(cat)}
              </button>
            ))}
            <p className="px-3 py-1.5 text-[9px] font-body text-brand-muted uppercase tracking-widest border-y border-brand-border">
              Expenses
            </p>
            {categories.expenses.map(cat => (
              <button
                key={cat}
                onClick={() => selectCategory(cat)}
                className={cn(
                  'w-full text-left text-[10px] font-body px-3 py-2 transition-colors',
                  cat === activeCategory
                    ? 'text-brand-text bg-brand-surface'
                    : 'text-brand-secondary hover:text-brand-text hover:bg-brand-surface',
                )}
              >
                {formatCategory(cat)}
              </button>
            ))}
          </div>
        )}
      </td>

      {/* Invoice match */}
      <td className="px-5 py-3 text-xs font-body text-brand-muted">
        {t.matched_invoice_id ? (
          <span className="text-[10px] font-body text-[#00C853]">matched</span>
        ) : '—'}
      </td>

      {/* Status */}
      <td className="px-5 py-3">
        <span className={cn('text-[10px] font-body px-2 py-1 rounded-sm border', statusStyle)}>
          {t.status}
        </span>
      </td>
    </tr>
  )
}
