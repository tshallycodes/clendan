'use client'

import { Fragment, useState } from 'react'
import { DownloadSimple } from '@phosphor-icons/react'
import { ReconciliationItem } from './types'
import { useCurrency } from '@/components/Providers'

interface ReconciliationTableProps {
  items: ReconciliationItem[]
  loading: boolean
  runId: string
  onExport: (runId: string) => void
}

function statusBadge(item: ReconciliationItem) {
  // AI assessment takes priority over raw DB status for display
  const aiAction = item.ai_action
  if (item.status === 'matched')
    return (
      <span className="px-2 py-0.5 rounded-sm text-[11px] font-body bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]">
        matched
      </span>
    )
  if (aiAction === 'flag')
    return (
      <span className="px-2 py-0.5 rounded-sm text-[11px] font-body bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]">
        flagged
      </span>
    )
  if (aiAction === 'review')
    return (
      <span className="px-2 py-0.5 rounded-sm text-[11px] font-body bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]">
        review
      </span>
    )
  if (aiAction === 'ok')
    return (
      <span className="px-2 py-0.5 rounded-sm text-[11px] font-body bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]">
        ok
      </span>
    )
  return (
    <span className="px-2 py-0.5 rounded-sm text-[11px] font-body bg-brand-elevated text-brand-muted border border-brand-border">
      {item.status}
    </span>
  )
}

export function ReconciliationTable({ items, loading, runId, onExport }: ReconciliationTableProps) {
  const { convert } = useCurrency()
  const [activeAccount, setActiveAccount] = useState<string>('all')
  const [activeFilter, setActiveFilter] = useState<string>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const accounts = Array.from(new Set(items.map((i) => i.account_name ?? i.account_id)))
  const tabs = ['all', ...accounts]

  const AI_FILTERS = [
    { key: 'all', label: 'All' },
    { key: 'flag', label: 'Flagged' },
    { key: 'review', label: 'Review' },
    { key: 'ok', label: 'OK' },
    { key: 'matched', label: 'Matched' },
  ]

  const byAccount = activeAccount === 'all' ? items : items.filter((i) => (i.account_name ?? i.account_id) === activeAccount)
  const visible = activeFilter === 'all'
    ? byAccount
    : activeFilter === 'matched'
      ? byAccount.filter((i) => i.status === 'matched')
      : byAccount.filter((i) => i.ai_action === activeFilter)

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
      {/* Header row: account tabs + AI filter + export */}
      <div className="flex flex-col gap-2 px-4 py-3 border-b border-brand-border">
        <div className="flex items-center justify-between gap-2">
          <div className="flex gap-1 flex-wrap">
            {tabs.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveAccount(tab)}
                className={`px-3 py-1 text-[11px] font-body rounded-sm transition-colors ${
                  activeAccount === tab
                    ? 'bg-brand-elevated text-brand-text'
                    : 'text-brand-muted hover:text-brand-secondary'
                }`}
              >
                {tab === 'all' ? 'All accounts' : tab}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => onExport(runId)}
            className="flex items-center gap-1.5 text-[11px] font-body text-brand-secondary border border-brand-border px-3 py-1.5 rounded-sm hover:text-brand-text hover:border-brand-text transition-colors shrink-0"
          >
            <DownloadSimple className="w-3 h-3" />
            Export CSV
          </button>
        </div>
        <div className="flex gap-1">
          {AI_FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setActiveFilter(f.key)}
              className={`px-3 py-1 text-[11px] font-body rounded-sm border transition-colors ${
                activeFilter === f.key
                  ? f.key === 'flag'
                    ? 'border-[#ff4d6d]/40 bg-[rgba(255,77,109,0.08)] text-[#ff4d6d]'
                    : f.key === 'review'
                      ? 'border-[#00a8cc]/40 bg-[rgba(0,168,204,0.08)] text-[#00a8cc]'
                      : f.key === 'ok' || f.key === 'matched'
                        ? 'border-[rgba(0,200,83,0.4)] bg-[rgba(0,200,83,0.08)] text-[#00C853]'
                        : 'border-brand-border bg-brand-elevated text-brand-text'
                  : 'border-transparent text-brand-muted hover:text-brand-secondary'
              }`}
            >
              {f.label}
              {f.key !== 'all' && (
                <span className="ml-1 opacity-60">
                  {f.key === 'matched'
                    ? items.filter((i) => i.status === 'matched').length
                    : items.filter((i) => i.ai_action === f.key).length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="p-8 text-center">
          <p className="text-xs font-body text-brand-muted">No items for this filter.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-body">
            <thead>
              <tr className="border-b border-brand-border">
                {['Date', 'Account', 'Description', 'Amount', 'Status', 'Invoice #', 'Vendor', 'Source', 'Agent Reasoning'].map(
                  (h) => (
                    <th key={h} className="px-3 py-2 text-left text-[11px] uppercase tracking-widest text-brand-muted font-body whitespace-nowrap">
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => {
                const isExpanded = expandedId === item.id
                const hasReasoning = !!item.reasoning
                return (
                  <Fragment key={item.id}>
                    <tr
                      onClick={() => hasReasoning && setExpandedId(isExpanded ? null : item.id)}
                      className={`border-b border-brand-border transition-colors ${hasReasoning ? 'cursor-pointer' : ''} hover:bg-brand-elevated ${
                        item.ai_action === 'flag' ? 'border-l border-l-[#ff4d6d]' :
                        item.ai_action === 'review' ? 'border-l border-l-[#00a8cc]' : ''
                      }`}
                    >
                      <td className="px-3 py-2 text-brand-secondary whitespace-nowrap">
                        {new Date(item.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })}
                      </td>
                      <td className="px-3 py-2 text-brand-text max-w-[120px] truncate" title={item.account_name ?? item.account_id}>
                        {item.account_name ?? item.account_id}
                      </td>
                      <td className="px-3 py-2 text-brand-text max-w-[160px] truncate" title={item.merchant_name ?? item.description}>
                        {item.merchant_name ?? item.description}
                      </td>
                      <td className={`px-3 py-2 whitespace-nowrap ${item.ai_action === 'flag' ? 'text-[#ff4d6d]' : 'text-brand-text'}`}>
                        {convert(item.amount_minor, item.currency)}
                      </td>
                      <td className="px-3 py-2">{statusBadge(item)}</td>
                      <td className="px-3 py-2 text-brand-secondary">{item.matched_invoice_number ?? '-'}</td>
                      <td className="px-3 py-2 text-brand-secondary max-w-[120px] truncate" title={item.matched_vendor ?? ''}>
                        {item.matched_vendor ?? '-'}
                      </td>
                      <td className="px-3 py-2">
                        {item.matched_source
                          ? <span className="px-2 py-0.5 rounded-sm text-[11px] font-body bg-brand-elevated text-brand-secondary border border-brand-border capitalize">{item.matched_source}</span>
                          : <span className="text-brand-muted">-</span>}
                      </td>
                      <td className="px-3 py-2 text-brand-muted max-w-[200px] truncate" title={item.reasoning}>
                        {item.reasoning
                          ? <span className="text-brand-muted">{item.reasoning.slice(0, 55)}{item.reasoning.length > 55 ? '… ↓' : ''}</span>
                          : '-'}
                      </td>
                    </tr>
                    {isExpanded && item.reasoning && (
                      <tr className="border-b border-brand-border bg-brand-elevated">
                        <td colSpan={9} className="px-4 py-3">
                          <p className={`text-[12px] font-body leading-relaxed ${item.ai_action === 'flag' ? 'text-[#ff4d6d]' : item.ai_action === 'review' ? 'text-[#00a8cc]' : 'text-brand-secondary'}`}>
                            {item.reasoning}
                          </p>
                          {item.ai_severity && (
                            <p className="text-[11px] font-body text-brand-muted mt-1">Severity: {item.ai_severity}</p>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
