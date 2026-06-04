import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { StatusBadge } from '@/components/dashboard/StatusBadge'
import { formatDate, formatTime } from '@/lib/utils'

interface Execution {
  id: string
  worker_type: string
  decision: string
  confidence: number
  status: string
  duration_ms: number | null
  created_at: string
}

interface ExecutionsData { executions: Execution[] }

export default async function ExecutionsPage() {
  let data: ExecutionsData | null = null
  try {
    const token = await getBackendToken()
    if (token) data = await apiGet<ExecutionsData>('/v1/dashboard/executions', token)
  } catch { /* backend not running */ }

  const executions = data?.executions ?? []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Execution Log</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">{executions.length} executions</p>
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
        {executions.length === 0 ? (
          <p className="px-5 py-12 text-xs font-mono text-brand-muted text-center">
            No executions yet — run a worker to see results here
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-brand-border">
                  {['Time', 'Worker', 'Decision', 'Confidence', 'Duration', 'Status'].map((h) => (
                    <th key={h} className="text-left text-[10px] font-mono text-brand-muted uppercase tracking-widest px-5 py-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {executions.map((e) => (
                  <tr key={e.id} className="border-b border-brand-border last:border-0 hover:bg-brand-elevated transition-colors">
                    <td className="px-5 py-3 text-xs font-mono text-brand-muted whitespace-nowrap">
                      {formatDate(e.created_at)} {formatTime(e.created_at)}
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-text">{e.worker_type.replace(/_/g, ' ')}</td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-text capitalize">{e.decision}</td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-secondary">
                      {(e.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-brand-muted">
                      {e.duration_ms != null ? `${e.duration_ms}ms` : '—'}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={e.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
