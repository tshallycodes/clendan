'use client'

import { useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { cn } from '@/lib/utils'
import { TransactionRow, type Transaction } from './TransactionRow'

export type { Transaction }

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const PAGE_SIZE = 50

type StatusFilter = 'all' | 'pending' | 'categorised' | 'matched'

const FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'categorised', label: 'Categorised' },
  { key: 'matched', label: 'Matched' },
]

interface Props {
  initialTransactions: Transaction[]
  total: number
}

export function TransactionsClient({ initialTransactions, total }: Props) {
  const { getToken } = useAuth()
  const [transactions, setTransactions] = useState(initialTransactions)
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [loadingMore, setLoadingMore] = useState(false)
  const [offset, setOffset] = useState(initialTransactions.length)

  const filtered = filter === 'all' ? transactions : transactions.filter(t => t.status === filter)

  function handleCategoryUpdate(id: string, category: string) {
    setTransactions(prev =>
      prev.map(t => t.id === id ? { ...t, ai_category: category, status: 'categorised' } : t)
    )
  }

  async function loadMore() {
    setLoadingMore(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(
        `${API_BASE}/v1/integrations/plaid/transactions?limit=${PAGE_SIZE}&offset=${offset}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!res.ok) return
      const json = await res.json()
      const next: Transaction[] = json.data?.transactions ?? []
      setTransactions(prev => [...prev, ...next])
      setOffset(prev => prev + next.length)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Transactions</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">{total} transactions total</p>
      </div>

      <div className="flex gap-1">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              'text-[10px] font-mono px-3 py-1.5 rounded-sm border transition-colors tracking-wider uppercase',
              filter === f.key
                ? 'border-brand-green/30 bg-brand-green/10 text-brand-green'
                : 'border-brand-border bg-transparent text-brand-muted hover:text-brand-text',
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {filtered.length === 0 ? (
          <p className="px-5 py-12 text-xs font-mono text-brand-muted text-center">
            No transactions yet — connect Plaid to import bank data
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-brand-border">
                  {['Date', 'Merchant', 'Amount', 'AI Category', 'Match', 'Status'].map((h, i) => (
                    <th key={i} className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-5 py-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(t => (
                  <TransactionRow key={t.id} transaction={t} onCategoryUpdate={handleCategoryUpdate} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {transactions.length < total && (
        <div className="flex justify-center">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="text-[10px] font-mono px-4 py-2 border border-brand-border text-brand-muted hover:text-brand-text transition-colors rounded-sm disabled:opacity-40"
          >
            {loadingMore ? 'Loading…' : 'Load more'}
          </button>
        </div>
      )}
    </div>
  )
}
