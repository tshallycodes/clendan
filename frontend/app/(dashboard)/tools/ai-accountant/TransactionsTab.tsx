'use client'

import { TransactionRow, type Transaction } from '@/components/dashboard/transactions/TransactionRow'
import { cn } from '@/lib/utils'

const TABLE_COLS = ['Date', 'Account', 'Merchant', 'Amount', 'Category', 'Invoice', 'Status']

export type StatusFilter = 'all' | 'pending' | 'categorised' | 'matched'
const FILTER_KEYS: StatusFilter[] = ['all', 'pending', 'categorised', 'matched']
const FILTER_LABELS: Record<StatusFilter, string> = {
  all: 'All', pending: 'Pending', categorised: 'Categorised', matched: 'Matched',
}

interface Props {
  transactions: Transaction[]
  total: number
  offset: number
  loadingMore: boolean
  filter: StatusFilter
  counts: Record<StatusFilter, number>
  categories: { income: string[]; expenses: string[] }
  running: boolean
  deployedId: string | null
  pendingCount: number
  onFilterChange: (f: StatusFilter) => void
  onCategoryUpdate: (id: string, category: string) => void
  onCategoriseNow: () => void
  onExportCsv: () => void
  onLoadMore: () => void
}

export function TransactionsTab({
  transactions, total, offset, loadingMore,
  filter, counts, categories, running, deployedId, pendingCount,
  onFilterChange, onCategoryUpdate, onCategoriseNow, onExportCsv, onLoadMore,
}: Props) {
  const filtered = filter === 'all' ? transactions : transactions.filter(t => t.status === filter)

  return (
    <div className="space-y-3">
      {/* Controls row */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex gap-1">
          {FILTER_KEYS.map(key => (
            <button key={key} type="button" onClick={() => onFilterChange(key)}
              className={cn(
                'text-[10px] font-mono px-3 py-1.5 rounded-sm border transition-colors uppercase tracking-wider',
                filter === key
                  ? 'border-[rgba(0,200,83,0.3)] bg-[rgba(0,200,83,0.08)] text-[#00C853]'
                  : 'border-brand-border text-brand-muted hover:text-brand-text',
              )}>
              {FILTER_LABELS[key]}
              <span className={cn('ml-1.5', filter === key ? 'text-brand-secondary' : 'text-brand-muted')}>
                {counts[key]}
              </span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onExportCsv}
            disabled={transactions.length === 0}
            className="text-xs font-mono border border-brand-border text-brand-muted hover:text-brand-text rounded-sm px-3 py-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Export CSV
          </button>
          <button
            type="button"
            onClick={onCategoriseNow}
            disabled={!deployedId || running || pendingCount === 0}
            className="text-xs font-mono bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-1.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {running ? 'Categorising…' : `Categorise Now (${pendingCount})`}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {filtered.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <p className="text-xs font-mono text-brand-muted">
              {transactions.length === 0
                ? 'No transactions yet — connect a bank account via Integrations.'
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
              <tbody>
                {filtered.map(t => (
                  <TransactionRow
                    key={t.id}
                    transaction={t}
                    onCategoryUpdate={onCategoryUpdate}
                    categories={categories}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Load more */}
      {offset < total && (
        <div className="flex justify-end">
          <button type="button" onClick={onLoadMore} disabled={loadingMore}
            className="text-[10px] font-mono px-4 py-2 border border-brand-border text-brand-muted hover:text-brand-text transition-colors rounded-sm disabled:opacity-60">
            {loadingMore ? 'Loading…' : `Load more (${total - offset} remaining)`}
          </button>
        </div>
      )}
    </div>
  )
}
