'use client'

import { motion } from 'framer-motion'

export type BarTone = 'positive' | 'negative' | 'neutral' | 'info' | 'warning'

export interface Bar {
  label: string
  value: number       // magnitude used for bar length (abs is taken)
  display: string     // formatted value shown as the direct label
  tone?: BarTone
}

const TONE_COLOR: Record<BarTone, string> = {
  positive: '#00C853',
  negative: '#ff4d6d',
  info:     '#00a8cc',
  warning:  '#f5a623',
  neutral:  '#5d6b7a', // brand-secondary-ish, reads monochrome
}

const EASE = [0.25, 0.46, 0.45, 0.94] as const

/** Dependency-free horizontal magnitude bars. Single series → no legend (the title names it). */
export function BarChart({ title, bars }: { title?: string; bars: Bar[] }) {
  const max = Math.max(1, ...bars.map((b) => Math.abs(b.value)))

  return (
    <div className="space-y-2.5">
      {title && <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{title}</p>}
      <div className="space-y-2">
        {bars.map((b, i) => {
          const pct = Math.round((Math.abs(b.value) / max) * 100)
          const color = TONE_COLOR[b.tone ?? 'neutral']
          return (
            <div key={b.label} className="grid grid-cols-[minmax(88px,120px)_1fr_auto] items-center gap-3 group">
              <span className="text-[11px] font-body text-brand-secondary truncate" title={b.label}>{b.label}</span>
              <div className="h-2.5 rounded-full bg-brand-elevated overflow-hidden group-hover:bg-brand-border/60 transition-colors">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.55, ease: EASE, delay: i * 0.05 }}
                  className="h-full rounded-full"
                  style={{ background: color }}
                />
              </div>
              <span className="text-[11px] font-body text-brand-text tabular-nums whitespace-nowrap">{b.display}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
