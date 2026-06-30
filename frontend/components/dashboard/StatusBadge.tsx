import { cn } from '@/lib/utils'

type Status = 'auto' | 'pending' | 'blocked' | 'active' | 'inactive' | 'connected' | 'error' | 'not_connected'

const BADGE_STYLES: Record<Status, { bg: string; text: string; border: string; label: string }> = {
  auto:          { bg: 'bg-[rgba(0,200,83,0.08)]',   text: 'text-brand-green',   border: 'border-[rgba(0,200,83,0.2)]',   label: 'AUTO' },
  pending:       { bg: 'bg-[rgba(0,168,204,0.08)]',  text: 'text-brand-info',    border: 'border-[rgba(0,168,204,0.2)]',  label: 'PENDING' },
  blocked:       { bg: 'bg-[rgba(255,77,109,0.08)]', text: 'text-brand-danger',  border: 'border-[rgba(255,77,109,0.2)]', label: 'BLOCKED' },
  active:        { bg: 'bg-[rgba(0,200,83,0.08)]',   text: 'text-brand-green',   border: 'border-[rgba(0,200,83,0.2)]',   label: 'ACTIVE' },
  inactive:      { bg: 'bg-transparent',              text: 'text-brand-muted',   border: 'border-brand-border',           label: 'INACTIVE' },
  connected:     { bg: 'bg-[rgba(0,200,83,0.08)]',   text: 'text-brand-green',   border: 'border-[rgba(0,200,83,0.2)]',   label: 'CONNECTED' },
  error:         { bg: 'bg-[rgba(255,77,109,0.08)]', text: 'text-brand-danger',  border: 'border-[rgba(255,77,109,0.2)]', label: 'ERROR' },
  not_connected: { bg: 'bg-transparent',              text: 'text-brand-muted',   border: 'border-brand-border',           label: 'NOT CONNECTED' },
}

export function StatusBadge({ status }: { status: Status | string }) {
  const style = BADGE_STYLES[status as Status] ?? BADGE_STYLES.inactive
  return (
    <span className={cn(
      'text-[11px] font-body font-medium border px-2 py-0.5 rounded-sm tracking-wider',
      style.bg, style.text, style.border,
    )}>
      {style.label}
    </span>
  )
}
