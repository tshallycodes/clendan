interface IntegrationSummary {
  name: string
  slug: string
  status: string
  last_synced_at: string | null
  summary?: string
}

const STATUS_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  connected: { bg: 'bg-[rgba(0,200,83,0.08)]',  text: 'text-[#00C853]', border: 'border-[rgba(0,200,83,0.2)]',  label: 'CONNECTED' },
  syncing:   { bg: 'bg-[rgba(0,168,204,0.08)]', text: 'text-[#00a8cc]', border: 'border-[rgba(0,168,204,0.2)]', label: 'SYNCING' },
  error:     { bg: 'bg-[rgba(255,77,109,0.08)]',text: 'text-[#ff4d6d]', border: 'border-[rgba(255,77,109,0.2)]',label: 'ERROR' },
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function IntegrationsHealth({ integrations }: { integrations: IntegrationSummary[] }) {
  const visible = integrations.filter((i) => i.status !== 'disconnected')

  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-brand-border">
        <h2 className="font-heading font-semibold text-brand-text text-sm">Integrations</h2>
        <p className="text-[11px] font-body text-brand-muted mt-0.5">Connected data sources your agents pull from — sync status and last activity</p>
      </div>
      {visible.length === 0 ? (
        <p className="px-5 py-8 text-xs font-body text-brand-muted text-center">
          No integrations connected — connect your accounting software and bank accounts
        </p>
      ) : (
        <div className="divide-y divide-brand-border">
          {visible.map((integration) => {
            const style = STATUS_STYLES[integration.status] ?? STATUS_STYLES.error
            return (
              <div key={integration.slug} className="px-5 py-3 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-body text-brand-text truncate">{integration.name}</div>
                  {integration.summary && (
                    <div className="text-[11px] font-body text-brand-muted">{integration.summary}</div>
                  )}
                </div>
                <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm border shrink-0 ${style.bg} ${style.text} ${style.border}`}>
                  {style.label}
                </span>
                <span className="text-[11px] font-body text-brand-muted shrink-0">
                  {integration.last_synced_at ? relativeTime(integration.last_synced_at) : '—'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
