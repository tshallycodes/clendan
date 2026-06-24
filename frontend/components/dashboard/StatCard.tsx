'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

function useCountUp(target: number, duration = 1200) {
  const [count, setCount] = useState(0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const start = performance.now()
    const step = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setCount(Math.floor(eased * target))
      if (progress < 1) rafRef.current = requestAnimationFrame(step)
      else setCount(target)
    }
    rafRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, duration])

  return count
}

interface StatCardProps {
  value: number | string
  label: string
  description?: string
  change?: string
  changeDirection?: 'up' | 'down' | 'neutral' | 'warning'
  delay?: number
}

export function StatCard({ value, label, description, change, changeDirection = 'neutral', delay = 0 }: StatCardProps) {
  const numeric = typeof value === 'number' ? value : null
  const animated = useCountUp(numeric ?? 0)
  const display = numeric !== null ? animated : value

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.38, delay, ease: [0.25, 0.46, 0.45, 0.94] as const }}
      className="bg-brand-surface border border-brand-border rounded-sm p-4"
    >
      <div className="font-heading text-3xl font-bold text-brand-text mb-1">{display}</div>
      <div className="text-brand-muted text-[10px] font-mono uppercase tracking-widest mb-1">{label}</div>
      {description && (
        <div className="text-brand-muted text-[10px] font-mono mb-2 leading-relaxed">{description}</div>
      )}
      {change && (
        <div className={cn('text-xs font-mono',
          changeDirection === 'up'      && 'text-brand-green',
          changeDirection === 'down'    && 'text-brand-danger',
          changeDirection === 'neutral' && 'text-brand-muted',
          changeDirection === 'warning' && 'text-brand-warning',
        )}>
          {changeDirection === 'up'   && '↑ '}
          {changeDirection === 'down' && '↓ '}
          {change}
        </div>
      )}
    </motion.div>
  )
}
