'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface DayData {
  date: string
  label: string
  auto: number
  pending: number
}

interface TooltipState {
  visible: boolean
  x: number
  y: number
  label: string
  auto: number
  pending: number
}

function BarGroup({ day, maxValue, animated }: { day: DayData; maxValue: number; animated: boolean }) {
  const autoH = maxValue > 0 ? (day.auto / maxValue) * 100 : 0
  const pendingH = maxValue > 0 ? (day.pending / maxValue) * 100 : 0

  return (
    <div className="group relative flex flex-col items-center gap-1 flex-1">
      <div
        className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 z-10
          bg-brand-elevated border border-brand-border rounded-sm px-3 py-2
          text-[11px] font-body text-brand-text whitespace-nowrap
          opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-150"
      >
        <div className="text-brand-muted mb-1">{day.label}</div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-none bg-brand-green" />
          <span className="text-brand-secondary">Auto:</span>
          <span className="text-brand-text">{day.auto}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-none bg-brand-info" />
          <span className="text-brand-secondary">Pending:</span>
          <span className="text-brand-text">{day.pending}</span>
        </div>
      </div>

      <div className="flex items-end gap-px w-full h-32">
        <div
          className="flex-1 bg-brand-green/70 rounded-none"
          style={{
            height: `${animated ? autoH : 0}%`,
            minHeight: autoH > 0 && animated ? 2 : 0,
            transition: 'height 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94)'
          }}
        />
        <div
          className="flex-1 bg-brand-info/70 rounded-none"
          style={{
            height: `${animated ? pendingH : 0}%`,
            minHeight: pendingH > 0 && animated ? 2 : 0,
            transition: 'height 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94) 0.1s'
          }}
        />
      </div>

      <span className="text-[11px] font-body text-brand-muted">{day.label}</span>
    </div>
  )
}

export function ExecutionChart() {
  const { getToken } = useAuth()
  const [data, setData] = useState<DayData[]>([])
  const [animated, setAnimated] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const token = await getToken()
        const res = await fetch(`${API}/dashboard/executions/chart?days=7`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const json = await res.json()
          setData(json.data?.chart ?? [])
        }
      } catch { /* chart is non-critical */ }
    }
    load()
  }, [getToken])

  useEffect(() => {
    if (data.length === 0) return
    const id = requestAnimationFrame(() => setAnimated(true))
    return () => cancelAnimationFrame(id)
  }, [data])

  const maxValue = Math.max(...data.map(d => d.auto + d.pending), 1)
  const isEmpty = data.every(d => d.auto === 0 && d.pending === 0)

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-brand-border flex items-center justify-between">
        <h2 className="font-heading font-semibold text-brand-text text-sm">Execution Activity</h2>
        <div className="flex items-center gap-4 text-[11px] font-body text-brand-muted">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 bg-brand-green/70" />
            Auto-executed
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 bg-brand-info/70" />
            Pending approval
          </span>
        </div>
      </div>

      <div className="px-5 py-5">
        {data.length === 0 || isEmpty ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <div className="w-full h-px bg-brand-border" />
            <p className="text-xs font-body text-brand-muted">No execution data yet</p>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            {data.map((day) => (
              <BarGroup key={day.date} day={day} maxValue={maxValue} animated={animated} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
