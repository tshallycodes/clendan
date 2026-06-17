'use client'

import { useState, useMemo } from 'react'
import { useAuth } from '@clerk/nextjs'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { TransactionRow, type Transaction } from './TransactionRow'

export type { Transaction }

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const PAGE_SIZE = 50

type StatusFilter = 'all' | 'pending' | 'categorised' | 'matched'

const FILTER_KEYS: StatusFilter[] = ['all', 'pending', 'categorised', 'matched']
const FILTER_LABELS: Record<StatusFilter, string> = {
  all:          'All',
  pending:      'Pending',
  categorised:  'Categorised',
  matched:      'Matched',
}

const TABLE_COLS = ['Date', 'Account', 'Merchant', 'Amount', 'Category', 'Invoice', 'Status']

const pageVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}

function formatSumCurrency(minor: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency', currency, maximumFractionDigits: 0,
    }).format(minor / 100)
  } catch {
    return `${(minor / 100).toFixed(0)} ${currency}`
  }
}

interface Props {
  initialTransactions: Transaction[]
  total: number
}

export function TransactionsClient({ initialTransactions, total }: Props) {
  const { getToken } = useAuth()
  const [transactions, setTransactions] = useState(initialTransactions)
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [search, setSearch] = useState('')
  const [loadingMore, setLoadingMore] = useState(false)
  const [offset, setOffset] = useState(initialTransactions.length)

  const counts = useMemo<Record<StatusFilter, number>>(() => {
    const c = { all: transactions.length, pending: 0, categorised: 0, matched: 0 }
    for (const t of transactions) {
      if (t.status in c) c[t.status as Exclude<StatusFilter, 'all'>]++
    }
    return c
  }, [transactions])

  const summary = useMemo(() => {
    const currency = transactions[0]?.currency ?? 'GBP'
    let totalOut = 0
    let totalIn = 0
    let debitCount = 0
    let creditCount = 0
    for (const t of transactions) {
      if (t.amount_minor > 0) { totalOut += t.amount_minor; debitCount++ }
      else { totalIn += Math.abs(t.amount_minor); creditCount++ }
    }
    return { totalOut, totalIn, net: totalIn - totalOut, currency, debitCount, creditCount }
  }, [transactions])

  const filtered = useMemo(() => {
    let result = filter === 'all' ? transactions : transactions.filter(t => t.status === filter)
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(t =>
        (t.merchant_name ?? '').toLowerCase().includes(q) ||
        (t.description ?? '').toLowerCase().includes(q)
      )
    }
    return result
  }, [transactions, filter, search])

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
        `${API_BASE}/v1/transactions?limit=${PAGE_SIZE}&offset=${offset}`,
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

  const { currency } = summary

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-6">

      {/* Header */}
      <motion.div variants={sectionVariants} className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Transactions</h1>
          <p className="text-brand-muted text-xs font-mono mt-1">
            {total} total · {transactions.length} loaded
          </p>
        </div>
        <input
          type="text"
          placeholder="Search merchant or description…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm px-3 py-1.5 text-xs font-mono w-64 outline-none transition-colors"
        />
      </motion.div>

      {/* Summary stats */}
      {transactions.length > 0 && (
        <motion.div variants={sectionVariants} className="grid grid-cols-3 gap-3">
          <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
            <p className="text-[10px] font-mono text-brand-muted uppercase tracking-wider">Total Out</p>
            <p className="text-xl font-mono font-semibold text-[#ff4d6d] mt-1">
              {formatSumCurrency(summary.totalOut, currency)}
            </p>
            <p className="text-[10px] font-mono text-brand-muted mt-1">
              {summary.debitCount} debit{summary.debitCount !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
            <p className="text-[10px] font-mono text-brand-muted uppercase tracking-wider">Total In</p>
            <p className="text-xl font-mono font-semibold text-[#00C853] mt-1">
              {formatSumCurrency(summary.totalIn, currency)}
            </p>
            <p className="text-[10px] font-mono text-brand-muted mt-1">
              {summary.creditCount} credit{summary.creditCount !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
            <p className="text-[10px] font-mono text-brand-muted uppercase tracking-wider">Net</p>
            <p className={cn(
              'text-xl font-mono font-semibold mt-1',
              summary.net >= 0 ? 'text-[#00C853]' : 'text-[#ff4d6d]',
            )}>
              {summary.net >= 0 ? '+' : '−'}{formatSumCurrency(Math.abs(summary.net), currency)}
            </p>
            <p className="text-[10px] font-mono text-brand-muted mt-1">
              {counts.pending} pending · {counts.matched} matched
            </p>
          </div>
        </motion.div>
      )}

      {/* Filter tabs */}
      <motion.div variants={sectionVariants} className="flex gap-1">
        {FILTER_KEYS.map(key => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={cn(
              'text-[10px] font-mono px-3 py-1.5 rounded-sm border transition-colors tracking-wider uppercase',
              filter === key
                ? 'border-brand-green/30 bg-brand-green/10 text-brand-green'
                : 'border-brand-border bg-transparent text-brand-muted hover:text-brand-text',
            )}
          >
            {FILTER_LABELS[key]}
            <span className={cn('ml-1.5', filter === key ? 'text-brand-green/60' : 'text-brand-muted/50')}>
              {counts[key]}
            </span>
          </button>
        ))}
      </motion.div>

      {/* Table */}
      <motion.div variants={sectionVariants} className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {filtered.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <p className="text-xs font-mono text-brand-muted">
              {transactions.length === 0
                ? 'No transactions yet — connect a bank account via Integrations to import data.'
                : search.trim()
                ? `No results for "${search}"`
                : 'No transactions match the selected filter.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-brand-border">
                  {TABLE_COLS.map(h => (
                    <th key={h} className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-5 py-3 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <motion.tbody initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4, delay: 0.2 }}>
                {filtered.map(t => (
                  <TransactionRow key={t.id} transaction={t} onCategoryUpdate={handleCategoryUpdate} />
                ))}
              </motion.tbody>
            </table>
          </div>
        )}
      </motion.div>

      {/* Pagination footer */}
      <motion.div variants={sectionVariants} className="flex items-center justify-between">
        <p className="text-[10px] font-mono text-brand-muted">
          {search.trim()
            ? `${filtered.length} result${filtered.length !== 1 ? 's' : ''} for "${search}"`
            : `Showing ${filtered.length} of ${total}`}
        </p>
        {transactions.length < total && (
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="text-[10px] font-mono px-4 py-2 border border-brand-border text-brand-muted hover:text-brand-text transition-colors rounded-sm disabled:opacity-40"
          >
            {loadingMore ? 'Loading…' : `Load more (${total - transactions.length} remaining)`}
          </button>
        )}
      </motion.div>

    </motion.div>
  )
}
