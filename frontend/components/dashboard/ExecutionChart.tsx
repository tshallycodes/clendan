'use client'

// TODO: wire to /v1/dashboard/executions?grouped_by=day

interface DayData {
  label: string
  auto: number
  pending: number
}

// Static placeholder data — replace with API response when endpoint is ready
const PLACEHOLDER_DATA: DayData[] = [
  { label: 'Mon', auto: 12, pending: 3 },
  { label: 'Tue', auto: 18, pending: 5 },
  { label: 'Wed', auto: 9,  pending: 8 },
  { label: 'Thu', auto: 24, pending: 2 },
  { label: 'Fri', auto: 20, pending: 6 },
  { label: 'Sat', auto: 6,  pending: 1 },
  { label: 'Sun', auto: 14, pending: 4 },
]

interface TooltipState {
  visible: boolean
  x: number
  y: number
  label: string
  auto: number
  pending: number
}

function BarGroup({ day, maxValue }: { day: DayData; maxValue: number }) {
  const autoH = maxValue > 0 ? (day.auto / maxValue) * 100 : 0
  const pendingH = maxValue > 0 ? (day.pending / maxValue) * 100 : 0

  return (
    <div className="group relative flex flex-col items-center gap-1 flex-1">
      {/* Tooltip */}
      <div
        className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 z-10
          bg-brand-elevated border border-brand-border rounded-sm px-3 py-2
          text-[10px] font-mono text-brand-text whitespace-nowrap
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

      {/* Bars */}
      <div className="flex items-end gap-px w-full h-32">
        <div
          className="flex-1 bg-brand-green/70 rounded-none transition-all duration-300"
          style={{ height: `${autoH}%`, minHeight: autoH > 0 ? 2 : 0 }}
        />
        <div
          className="flex-1 bg-brand-info/70 rounded-none transition-all duration-300"
          style={{ height: `${pendingH}%`, minHeight: pendingH > 0 ? 2 : 0 }}
        />
      </div>

      <span className="text-[10px] font-mono text-brand-muted">{day.label}</span>
    </div>
  )
}

export function ExecutionChart() {
  const data = PLACEHOLDER_DATA
  const maxValue = Math.max(...data.map(d => d.auto + d.pending), 1)
  const isEmpty = data.every(d => d.auto === 0 && d.pending === 0)

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-brand-border flex items-center justify-between">
        <h2 className="font-heading font-semibold text-brand-text text-sm">Execution Activity</h2>
        <div className="flex items-center gap-4 text-[10px] font-mono text-brand-muted">
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
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <div className="w-full h-px bg-brand-border" />
            <p className="text-xs font-mono text-brand-muted">No execution data yet</p>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            {data.map((day) => (
              <BarGroup key={day.label} day={day} maxValue={maxValue} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
