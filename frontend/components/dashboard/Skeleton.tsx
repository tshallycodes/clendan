import { cn } from '@/lib/utils'

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn('relative overflow-hidden rounded-sm bg-brand-elevated', className)}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.6s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" />
    </div>
  )
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-px">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 px-5 py-3 border-b border-brand-border">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-32 flex-1" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-5 w-16" />
        </div>
      ))}
    </div>
  )
}
