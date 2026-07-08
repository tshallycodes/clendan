'use client'

import { useState } from 'react'
import { useToast } from '@/components/Providers'

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

const STORAGE_KEY = 'clendan:notifications'

function loadFromStorage(): Record<string, boolean> {
  const defaults = Object.fromEntries(ROWS.map((r) => [r.id, r.defaultOn]))
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...defaults, ...JSON.parse(raw) }
  } catch {
    // SSR or malformed JSON - fall through to defaults
  }
  return defaults
}

export function NotificationsSection() {
  const { toast } = useToast()
  const [values, setValues] = useState<Record<string, boolean>>(loadFromStorage)

  function toggle(id: string) {
    setValues((prev) => {
      const next = { ...prev, [id]: !prev[id] }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        // storage unavailable - state still updated in memory
      }
      const row = ROWS.find(r => r.id === id)
      if (row) toast(`${row.label} ${next[id] ? 'enabled' : 'disabled'}`, 'success')
      return next
    })
  }

  return (
    <div className="space-y-3">
      {ROWS.map((row) => (
        <div key={row.id} className="flex items-center justify-between py-1">
          <span className="text-xs font-body text-brand-text">{row.label}</span>
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
