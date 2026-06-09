'use client'

import { useState } from 'react'

interface ToggleRow {
  id: string
  label: string
  defaultOn: boolean
}

const ROWS: ToggleRow[] = [
  { id: 'email_approval', label: 'Email on approval request', defaultOn: true },
  { id: 'email_blocked', label: 'Email on blocked execution', defaultOn: false },
  { id: 'weekly_summary', label: 'Weekly execution summary', defaultOn: true },
]

export function NotificationsSection() {
  const [values, setValues] = useState<Record<string, boolean>>(
    Object.fromEntries(ROWS.map((r) => [r.id, r.defaultOn]))
  )

  function toggle(id: string) {
    setValues((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  return (
    <div className="space-y-3">
      {ROWS.map((row) => (
        <div key={row.id} className="flex items-center justify-between py-1">
          <span className="text-xs font-mono text-brand-text">{row.label}</span>
          <button
            type="button"
            role="switch"
            aria-checked={values[row.id] ? 'true' : 'false'}
            aria-label={row.label}
            onClick={() => toggle(row.id)}
            className={[
              'relative w-10 h-5 rounded-full transition-colors duration-200',
              values[row.id] ? 'bg-brand-green' : 'bg-[#2a3a2a]',
            ].join(' ')}
          >
            <span
              className={[
                'absolute top-[2px] left-[2px] h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200',
                values[row.id] ? 'translate-x-[20px]' : 'translate-x-0',
              ].join(' ')}
            />
          </button>
        </div>
      ))}
    </div>
  )
}
