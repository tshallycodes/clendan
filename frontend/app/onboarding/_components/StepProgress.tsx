'use client'

interface StepProgressProps {
  current: number
  total: number
}

export function StepProgress({ current, total }: StepProgressProps) {
  return (
    <div className="flex items-center justify-center gap-2 mb-10">
      {Array.from({ length: total }, (_, i) => i + 1).map((n) => (
        <div
          key={n}
          className={[
            'w-2 h-2 rounded-full transition-colors duration-200',
            n === current ? 'bg-brand-green' : 'bg-brand-border',
          ].join(' ')}
        />
      ))}
    </div>
  )
}
