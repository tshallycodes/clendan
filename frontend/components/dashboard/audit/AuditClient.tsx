'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { AuditFilters } from './AuditFilters'
import { AuditTable, exportCsv } from './AuditTable'
import type { AuditEntry } from './AuditTable'

interface Props {
  entries: AuditEntry[]
}

export function AuditClient({ entries }: Props) {
  const [searchQuery, setSearchQuery] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const sectionVariants = {
    hidden: { opacity: 0, y: 14 },
    show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: [0.25, 0.46, 0.45, 0.94] as const } },
  }

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.07 } } }}
      className="space-y-4"
    >
      <motion.div variants={sectionVariants} className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <AuditFilters
          searchQuery={searchQuery}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onSearchChange={setSearchQuery}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
        />
        <button
          onClick={() => exportCsv(entries)}
          className="shrink-0 bg-transparent border border-brand-border text-brand-text hover:bg-brand-elevated
            text-xs font-body px-4 py-2 rounded-sm transition-colors"
        >
          Export CSV
        </button>
      </motion.div>

      <motion.div variants={sectionVariants} className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {entries.length === 0 ? (
          <p className="px-5 py-12 text-xs font-body text-brand-muted text-center">No audit entries yet</p>
        ) : (
          <AuditTable
            entries={entries}
            searchQuery={searchQuery}
            dateFrom={dateFrom}
            dateTo={dateTo}
          />
        )}
      </motion.div>
    </motion.div>
  )
}
