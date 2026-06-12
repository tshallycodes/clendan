'use client'

import { useState } from 'react'
import { Download } from 'lucide-react'
import { ReconciliationItem } from './types'

interface ReconciliationTableProps {
  items: ReconciliationItem[]
  loading: boolean
  runId: string
  onExport: (runId: string) => void
}

function statusBadge(status: string) {
  if (status === 'matched')
    return (
      <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]">
        matched
      </span>
    )
  if (status === 'flagged')
    return (
      <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]">
        flagged
      </span>
    )
  if (status === 'review')
    return (
      <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]">
        review
      </span>
    )
  return (
    <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono bg-[rgba(74,106,74,0.08)] text-[#4a6a4a] border border-[rgba(74,106,74,0.2)]">
      {status}
    </span>
  )
}

function formatAmount(amount_minor: number, currency: string) {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount_minor / 100)
}

export function ReconciliationTable({ items, loading, runId, onExport }: ReconciliationTableProps) {
  const [activeAccount, setActiveAccount] = useState<string>('all')

  const accounts = Array.from(new Set(items.map((i) => i.account_name ?? i.account_id)))
  const tabs = ['all', ...accounts]

  const visible =
    activeAccount === 'all' ? items : items.filter((i) => (i.account_name ?? i.account_id) === activeAccount)

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-10 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      {/* Header row: tabs + export */}
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-brand-border">
        <div className="flex gap-1 flex-wrap">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveAccount(tab)}
              className={`px-3 py-1 text-[10px] font-mono rounded-sm transition-colors ${
                activeAccount === tab
                  ? 'bg-brand-elevated text-brand-text'
                  : 'text-brand-muted hover:text-brand-secondary'
              }`}
            >
              {tab === 'all' ? 'All' : tab}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => onExport(runId)}
          className="flex items-center gap-1.5 text-[10px] font-mono text-brand-secondary border border-brand-border px-3 py-1.5 rounded-sm hover:text-brand-text hover:border-brand-text transition-colors"
        >
          <Download className="w-3 h-3" />
          Export CSV
        </button>
      </div>

      {visible.length === 0 ? (
        <div className="p-8 text-center">
          <p className="text-xs font-mono text-brand-muted">No items for this filter.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-brand-border">
                {['Date', 'Account', 'Description', 'Amount', 'Status', 'Invoice #', 'Vendor', 'Reasoning'].map(
                  (h) => (
                    <th key={h} className="px-3 py-2 text-left text-[10px] uppercase tracking-widest text-brand-muted font-mono whitespace-nowrap">
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => (
                <tr key={item.id} className="border-b border-brand-border hover:bg-brand-elevated transition-colors">
                  <td className="px-3 py-2 text-brand-secondary whitespace-nowrap">
                    {new Date(item.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })}
                  </td>
                  <td className="px-3 py-2 text-brand-text max-w-[120px] truncate" title={item.account_name ?? item.account_id}>
                    {item.account_name ?? item.account_id}
                  </td>
                  <td className="px-3 py-2 text-brand-text max-w-[160px] truncate" title={item.merchant_name ?? item.description}>
                    {item.merchant_name ?? item.description}
                  </td>
                  <td className="px-3 py-2 text-brand-text whitespace-nowrap">
                    {formatAmount(item.amount_minor, item.currency)}
                  </td>
                  <td className="px-3 py-2">{statusBadge(item.status)}</td>
                  <td className="px-3 py-2 text-brand-secondary">{item.matched_invoice_number ?? '—'}</td>
                  <td className="px-3 py-2 text-brand-secondary max-w-[120px] truncate" title={item.matched_vendor ?? ''}>
                    {item.matched_vendor ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-brand-muted max-w-[180px] truncate" title={item.reasoning}>
                    {item.reasoning ? item.reasoning.slice(0, 60) + (item.reasoning.length > 60 ? '…' : '') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
