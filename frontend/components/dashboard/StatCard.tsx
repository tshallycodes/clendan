'use client'

import { useEffect, useRef, useState } from 'react'
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
  change?: string
  changeDirection?: 'up' | 'down' | 'neutral'
}

export function StatCard({ value, label, change, changeDirection = 'neutral' }: StatCardProps) {
  const numeric = typeof value === 'number' ? value : null
  const animated = useCountUp(numeric ?? 0)
  const display = numeric !== null ? animated : value

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4">
      <div className="font-heading text-3xl font-bold text-brand-text mb-1">{display}</div>
      <div className="text-brand-muted text-[10px] font-mono uppercase tracking-widest mb-2">{label}</div>
      {change && (
        <div className={cn('text-xs font-mono',
          changeDirection === 'up' && 'text-brand-green',
          changeDirection === 'down' && 'text-brand-danger',
          changeDirection === 'neutral' && 'text-brand-muted',
        )}>
          {changeDirection === 'up' && '↑ '}
          {changeDirection === 'down' && '↓ '}
          {change}
        </div>
      )}
    </div>
  )
}
