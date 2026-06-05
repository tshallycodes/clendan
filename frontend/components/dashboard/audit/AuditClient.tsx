'use client'

import { useState } from 'react'
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

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
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
          className="shrink-0 bg-transparent border border-brand-border text-brand-text hover:bg-brand-surface
            text-xs font-mono px-4 py-2 rounded-sm transition-colors"
        >
          Export CSV
        </button>
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {entries.length === 0 ? (
          <p className="px-5 py-12 text-xs font-mono text-brand-muted text-center">No audit entries yet</p>
        ) : (
          <AuditTable
            entries={entries}
            searchQuery={searchQuery}
            dateFrom={dateFrom}
            dateTo={dateTo}
          />
        )}
      </div>
    </div>
  )
}
