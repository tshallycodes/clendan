interface Worker {
  id: string
  type: string
  autonomy_level: 'auto' | 'approve' | 'suggest'
  status: 'active' | 'inactive'
  version: number
}

function formatType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

const autonomyBadge: Record<Worker['autonomy_level'], { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-brand-green border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-brand-info border border-[rgba(0,168,204,0.2)]' },
  suggest: { label: 'Suggest', className: 'bg-brand-surface text-brand-muted border border-brand-border' },
}

export function WorkerCard({ worker }: { worker: Worker }) {
  const isActive = worker.status === 'active'
  const badge = autonomyBadge[worker.autonomy_level]

  return (
    <div
      className={[
        'bg-brand-surface border border-brand-border rounded-sm p-4 flex items-center gap-4',
        isActive ? 'border-l-[3px] border-l-brand-green' : '',
      ].join(' ')}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-mono text-brand-text font-medium">
            {formatType(worker.type)}
          </span>
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${badge.className}`}>
            {badge.label}
          </span>
        </div>
        <div className="text-xs font-mono text-brand-muted mt-0.5">v{worker.version}</div>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        {isActive ? (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-green opacity-60" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-green" />
          </span>
        ) : (
          <span className="h-2 w-2 rounded-full bg-brand-muted" />
        )}
        <span className={`text-xs font-mono ${isActive ? 'text-brand-green' : 'text-brand-muted'}`}>
          {isActive ? 'Active' : 'Inactive'}
        </span>
      </div>
    </div>
  )
}
