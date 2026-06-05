'use client'

interface Props {
  searchQuery: string
  dateFrom: string
  dateTo: string
  onSearchChange: (v: string) => void
  onDateFromChange: (v: string) => void
  onDateToChange: (v: string) => void
}

export function AuditFilters({
  searchQuery,
  dateFrom,
  dateTo,
  onSearchChange,
  onDateFromChange,
  onDateToChange,
}: Props) {
  const inputClass =
    'bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text placeholder:text-brand-muted outline-none transition-colors'

  return (
    <div className="flex flex-col sm:flex-row gap-2">
      <input
        type="text"
        placeholder="Search by trace ID, actor, action..."
        value={searchQuery}
        onChange={e => onSearchChange(e.target.value)}
        className={`${inputClass} flex-1`}
      />
      <input
        type="date"
        value={dateFrom}
        onChange={e => onDateFromChange(e.target.value)}
        className={`${inputClass} w-auto`}
        title="From date"
      />
      <input
        type="date"
        value={dateTo}
        onChange={e => onDateToChange(e.target.value)}
        className={`${inputClass} w-auto`}
        title="To date"
      />
    </div>
  )
}
