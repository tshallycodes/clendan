'use client'

interface Props {
  pathname: string
}

const CONTEXT_MAP: Record<string, string> = {
  '/approvals': 'I can see your pending approvals',
  '/executions': 'I can see your execution log',
  '/dashboard/integrations': 'I can see your connected integrations',
  '/transactions': 'I can see your bank transactions',
  '/dashboard': 'I can see your dashboard overview',
}

function getContext(pathname: string): string {
  for (const [route, label] of Object.entries(CONTEXT_MAP)) {
    if (pathname === route || pathname.startsWith(route + '/')) return label
  }
  return 'I can see your account'
}

export function ClenContextBar({ pathname }: Props) {
  const label = getContext(pathname)

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-brand-border bg-brand-bg">
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-40" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00C853]" />
      </span>
      <span className="text-[11px] font-mono text-brand-muted">{label}</span>
    </div>
  )
}
