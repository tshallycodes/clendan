'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { TransactionRow, type Transaction } from '@/components/dashboard/transactions/TransactionRow'
import { cn } from '@/lib/utils'

export type StatusFilter = 'all' | 'pending' | 'categorised' | 'matched'
const FILTER_KEYS: StatusFilter[] = ['all', 'pending', 'categorised', 'matched']
const FILTER_LABELS: Record<StatusFilter, string> = {
  all: 'All', pending: 'Pending', categorised: 'Categorised', matched: 'Matched',
}

/* ── Column filter types ─────────────────────────────────────────── */
type ColumnFilterKey = 'account' | 'merchant' | 'category' | 'invoice' | 'status'

/* Column order must match TransactionRow: Date, Account, Merchant, Amount, Category, Invoice, Status */
type ColumnDef = { header: string; filterKey?: ColumnFilterKey }
const TABLE_COLUMNS: ColumnDef[] = [
  { header: 'Date' },
  { header: 'Account',  filterKey: 'account' },
  { header: 'Merchant', filterKey: 'merchant' },
  { header: 'Amount' },
  { header: 'Category', filterKey: 'category' },
  { header: 'Invoice',  filterKey: 'invoice' },
  { header: 'Status',   filterKey: 'status' },
]

function formatCategory(raw: string): string {
  return raw.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/* ── Funnel icon (inline SVG) ────────────────────────────────────── */
function FunnelIcon({ active }: { active: boolean }) {
  return (
    <svg
      width="10" height="10" viewBox="0 0 16 16" fill="none"
      className={cn(
        'shrink-0 transition-colors',
        active ? 'text-[#00C853]' : 'text-brand-muted group-hover:text-brand-secondary',
      )}
    >
      <path
        d="M1.5 2h13l-5 6v4.5l-3 1.5V8L1.5 2Z"
        fill="currentColor" fillOpacity={active ? 0.5 : 0.2}
        stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"
      />
    </svg>
  )
}

/* ── Column-filter dropdown ──────────────────────────────────────── */
interface ColumnFilterDropdownProps {
  header: string
  columnKey: ColumnFilterKey
  options: string[]
  selected: Set<string>
  onToggle: (value: string) => void
  onClear: () => void
  onSelectAll: () => void
}

function ColumnFilterDropdown({
  header, columnKey, options, selected, onToggle, onClear, onSelectAll,
}: ColumnFilterDropdownProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const filtered = useMemo(() => {
    if (!search) return options
    const q = search.toLowerCase()
    return options.filter(o => o.toLowerCase().includes(q))
  }, [options, search])

  const active = selected.size > 0

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        onClick={() => { setOpen(v => !v); setSearch('') }}
        className={cn(
          'group inline-flex items-center gap-1 text-left text-[10px] font-mono uppercase tracking-widest transition-colors',
          active ? 'text-[#00C853]' : 'text-brand-muted hover:text-brand-secondary',
        )}
      >
        {header}
        <FunnelIcon active={active} />
        {active && (
          <span className="text-[8px] font-mono bg-[rgba(0,200,83,0.12)] text-[#00C853] rounded-full px-1 min-w-[14px] text-center leading-[14px]">
            {selected.size}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1.5 z-40 w-56 bg-brand-elevated border border-brand-border rounded-sm overflow-hidden">
          {/* Search */}
          {options.length > 5 && (
            <div className="px-2.5 py-2 border-b border-brand-border">
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder={`Search ${header.toLowerCase()}…`}
                className="w-full text-[10px] font-mono bg-brand-surface border border-brand-border rounded-sm px-2 py-1.5 text-brand-text placeholder:text-brand-muted outline-none focus:border-[#00C853] transition-colors"
                autoFocus
              />
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-1 px-2.5 py-1.5 border-b border-brand-border">
            <button
              type="button"
              onClick={onSelectAll}
              className="text-[9px] font-mono text-brand-muted hover:text-brand-secondary transition-colors"
            >
              Select all
            </button>
            <span className="text-[9px] text-brand-muted">·</span>
            <button
              type="button"
              onClick={onClear}
              className="text-[9px] font-mono text-brand-muted hover:text-brand-secondary transition-colors"
            >
              Clear
            </button>
          </div>

          {/* Options */}
          <div className="max-h-48 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-3 py-3 text-[10px] font-mono text-brand-muted text-center">No matches</p>
            ) : (
              filtered.map(opt => {
                const isSelected = selected.has(opt)
                return (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => onToggle(opt)}
                    className={cn(
                      'w-full flex items-center gap-2 text-left text-[10px] font-mono px-3 py-1.5 transition-colors',
                      isSelected
                        ? 'text-brand-text bg-brand-surface'
                        : 'text-brand-secondary hover:text-brand-text hover:bg-brand-surface',
                    )}
                  >
                    {/* Checkbox indicator */}
                    <span className={cn(
                      'shrink-0 w-3 h-3 rounded-sm border flex items-center justify-center transition-colors',
                      isSelected
                        ? 'bg-[#00C853] border-[#00C853]'
                        : 'border-brand-border',
                    )}>
                      {isSelected && (
                        <svg width="8" height="8" viewBox="0 0 12 12" fill="none">
                          <path d="M2.5 6L5 8.5L9.5 3.5" stroke="black" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </span>
                    <span className="truncate">
                      {columnKey === 'category' ? formatCategory(opt) : opt}
                    </span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Helper: extract unique column values ────────────────────────── */
function getColumnValue(t: Transaction, key: ColumnFilterKey): string {
  switch (key) {
    case 'account':
      return t.account_name ?? '—'
    case 'merchant':
      return t.merchant_name ?? t.description ?? '—'
    case 'category':
      return t.ai_category ?? t.plaid_category ?? '—'
    case 'invoice':
      return t.matched_invoice_id ? 'Matched' : 'Unmatched'
    case 'status':
      return t.status
  }
}

function getUniqueValues(transactions: Transaction[], key: ColumnFilterKey): string[] {
  const set = new Set<string>()
  for (const t of transactions) set.add(getColumnValue(t, key))
  return Array.from(set).sort((a, b) => a.localeCompare(b))
}

/* ── Main component ──────────────────────────────────────────────── */
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
  /* ── Column filter state ─────────────────────────────────────── */
  const [columnFilters, setColumnFilters] = useState<Record<ColumnFilterKey, Set<string>>>({
    account: new Set(), merchant: new Set(), category: new Set(), invoice: new Set(), status: new Set(),
  })

  const toggleFilter = useCallback((key: ColumnFilterKey, value: string) => {
    setColumnFilters(prev => {
      const s = new Set(prev[key])
      if (s.has(value)) s.delete(value)
      else s.add(value)
      return { ...prev, [key]: s }
    })
  }, [])

  const clearFilter = useCallback((key: ColumnFilterKey) => {
    setColumnFilters(prev => ({ ...prev, [key]: new Set() }))
  }, [])

  const selectAllFilter = useCallback((key: ColumnFilterKey, options: string[]) => {
    setColumnFilters(prev => ({ ...prev, [key]: new Set(options) }))
  }, [])

  const clearAllFilters = useCallback(() => {
    setColumnFilters({
      account: new Set(), merchant: new Set(), category: new Set(), invoice: new Set(), status: new Set(),
    })
  }, [])

  /* ── Derived: unique values per column ───────────────────────── */
  const columnOptions = useMemo(() => {
    const result: Record<ColumnFilterKey, string[]> = {
      account: [], merchant: [], category: [], invoice: [], status: [],
    }
    for (const col of TABLE_COLUMNS) {
      if (col.filterKey) result[col.filterKey] = getUniqueValues(transactions, col.filterKey)
    }
    return result
  }, [transactions])

  /* ── Derived: active filter count ────────────────────────────── */
  const activeFilterCount = useMemo(() => {
    let count = 0
    for (const key of Object.keys(columnFilters) as ColumnFilterKey[]) {
      count += columnFilters[key].size
    }
    return count
  }, [columnFilters])

  /* ── Apply column filters ────────────────────────────────────── */
  const filtered = useMemo(() => {
    if (activeFilterCount === 0) return transactions
    return transactions.filter(t => {
      for (const key of Object.keys(columnFilters) as ColumnFilterKey[]) {
        const set = columnFilters[key]
        if (set.size === 0) continue
        if (!set.has(getColumnValue(t, key))) return false
      }
      return true
    })
  }, [transactions, columnFilters, activeFilterCount])

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
          {/* Clear column filters */}
          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={clearAllFilters}
              className="text-[10px] font-mono text-brand-muted hover:text-brand-secondary transition-colors flex items-center gap-1"
            >
              <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="text-current">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              Clear {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''}
            </button>
          )}
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
        {filtered.length === 0 && activeFilterCount === 0 ? (
          <div className="px-5 py-16 text-center">
            <p className="text-xs font-mono text-brand-muted">
              {filter === 'all'
                ? 'No transactions yet — connect a bank account via Integrations.'
                : `No ${filter} transactions.`}
            </p>
          </div>
        ) : filtered.length === 0 && activeFilterCount > 0 ? (
          <div className="px-5 py-16 text-center space-y-2">
            <p className="text-xs font-mono text-brand-muted">
              No transactions match the current column filters.
            </p>
            <button
              type="button"
              onClick={clearAllFilters}
              className="text-[10px] font-mono text-brand-muted hover:text-brand-secondary transition-colors"
            >
              Clear all filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-brand-border">
                  {TABLE_COLUMNS.map(col => (
                    <th key={col.header} className="text-left px-5 py-3 whitespace-nowrap">
                      {col.filterKey ? (
                        <ColumnFilterDropdown
                          header={col.header}
                          columnKey={col.filterKey}
                          options={columnOptions[col.filterKey]}
                          selected={columnFilters[col.filterKey]}
                          onToggle={(v) => toggleFilter(col.filterKey!, v)}
                          onClear={() => clearFilter(col.filterKey!)}
                          onSelectAll={() => selectAllFilter(col.filterKey!, columnOptions[col.filterKey!])}
                        />
                      ) : (
                        <span className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">
                          {col.header}
                        </span>
                      )}
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
