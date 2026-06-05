'use client'

import { useState } from 'react'

// TODO: wire to notifications API

interface ToggleRow {
  id: string
  label: string
  defaultOn: boolean
}

const ROWS: ToggleRow[] = [
  { id: 'email_approval', label: 'Email on approval request', defaultOn: true },
  { id: 'email_blocked', label: 'Email on blocked execution', defaultOn: true },
  { id: 'weekly_summary', label: 'Weekly execution summary', defaultOn: false },
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
            aria-checked={values[row.id]}
            onClick={() => toggle(row.id)}
            className={[
              'relative w-10 h-5 rounded-full transition-colors border',
              values[row.id]
                ? 'bg-brand-green border-brand-green'
                : 'bg-brand-bg border-brand-border',
            ].join(' ')}
          >
            <span
              className={[
                'absolute top-0.5 h-4 w-4 rounded-full bg-black transition-transform',
                values[row.id] ? 'translate-x-5' : 'translate-x-0.5',
              ].join(' ')}
            />
          </button>
        </div>
      ))}
    </div>
  )
}
