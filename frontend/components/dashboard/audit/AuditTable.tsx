'use client'

import { Fragment, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export interface AuditEntry {
  id: string
  actor: string
  action: string
  model_version: string
  created_at: string
  execution_id: string | null
  reasoning_trace_json?: unknown
}

interface Props {
  entries: AuditEntry[]
  searchQuery: string
  dateFrom: string
  dateTo: string
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  const date = d.toLocaleDateString('en-CA') // YYYY-MM-DD
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  return `${date} ${time}`
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="ml-1 text-brand-muted hover:text-brand-text transition-colors"
      title="Copy trace ID"
      aria-label="Copy trace ID"
    >
      {copied ? (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
          <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 0 1 1.06-1.06L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0z" />
        </svg>
      ) : (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
          <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z" />
          <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z" />
        </svg>
      )}
    </button>
  )
}

export function exportCsv(entries: AuditEntry[]) {
  const rows = [
    ['Timestamp', 'Actor', 'Action', 'Decision', 'Trace ID'],
    ...entries.map(e => [e.created_at, e.actor, e.action, e.execution_id ?? '', e.id]),
  ]
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'audit-log.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export function AuditTable({ entries, searchQuery, dateFrom, dateTo }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    return entries.filter(e => {
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        const match =
          e.id.toLowerCase().includes(q) ||
          e.actor.toLowerCase().includes(q) ||
          e.action.toLowerCase().includes(q)
        if (!match) return false
      }
      if (dateFrom) {
        const from = new Date(dateFrom)
        if (new Date(e.created_at) < from) return false
      }
      if (dateTo) {
        const to = new Date(dateTo)
        to.setHours(23, 59, 59, 999)
        if (new Date(e.created_at) > to) return false
      }
      return true
    })
  }, [entries, searchQuery, dateFrom, dateTo])

  if (filtered.length === 0) {
    return (
      <div className="px-5 py-12 text-xs font-mono text-brand-muted text-center">
        No audit entries match your filters
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-brand-border">
            <th className="px-5 py-3 text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest">Timestamp</th>
            <th className="px-5 py-3 text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest">Actor</th>
            <th className="px-5 py-3 text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest">Action</th>
            <th className="px-5 py-3 text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest">Decision</th>
            <th className="px-5 py-3 text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest">Trace ID</th>
            <th className="px-5 py-3 text-right text-[10px] font-mono text-brand-muted uppercase tracking-widest" aria-label="Expand row" />
          </tr>
        </thead>
        <motion.tbody
          className="divide-y divide-brand-border"
          initial="hidden"
          animate="show"
          variants={{ hidden: {}, show: { transition: { staggerChildren: 0.04 } } }}
        >
          {filtered.map(e => {
            const isExpanded = expandedId === e.id
            return (
              <Fragment key={e.id}>
                <motion.tr
                  variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { duration: 0.2 } } }}
                  onClick={() => setExpandedId(isExpanded ? null : e.id)}
                  className="hover:bg-brand-elevated transition-colors cursor-pointer"
                >
                  <td className="px-5 py-3 text-brand-muted whitespace-nowrap">
                    {formatTimestamp(e.created_at)}
                  </td>
                  <td className="px-5 py-3 text-brand-text">{e.actor}</td>
                  <td className="px-5 py-3 text-brand-secondary">{e.action}</td>
                  <td className="px-5 py-3 text-brand-muted">
                    {e.execution_id ? (
                      <span className="text-brand-muted/70">{e.execution_id.slice(0, 8)}…</span>
                    ) : (
                      <span className="text-brand-muted/40">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    <span className="flex items-center gap-1">
                      <span className="text-brand-muted">{e.id.slice(0, 8)}…</span>
                      <CopyButton text={e.id} />
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right text-brand-muted">
                    {isExpanded ? '↑' : '↓'}
                  </td>
                </motion.tr>
                <AnimatePresence>
                  {isExpanded && (
                    <motion.tr
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.15 }}
                      className="bg-brand-bg"
                    >
                      <td colSpan={6} className="px-5 py-4">
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.22, ease: 'easeOut' }}
                          className="overflow-hidden"
                        >
                          <pre className="bg-brand-bg border border-brand-border rounded-sm p-4 text-xs font-mono text-brand-secondary overflow-x-auto whitespace-pre-wrap break-all">
                            {e.reasoning_trace_json
                              ? JSON.stringify(e.reasoning_trace_json, null, 2)
                              : '— no reasoning trace recorded —'}
                          </pre>
                        </motion.div>
                      </td>
                    </motion.tr>
                  )}
                </AnimatePresence>
              </Fragment>
            )
          })}
        </motion.tbody>
      </table>
    </div>
  )
}
