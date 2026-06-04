import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { WorkerCard } from '@/components/dashboard/workers/WorkerCard'
import { DeployWorkerForm } from '@/components/dashboard/workers/DeployWorkerForm'

interface Worker {
  id: string
  type: string
  autonomy_level: 'auto' | 'approve' | 'suggest'
  status: 'active' | 'inactive'
  version: number
}

export default async function WorkersPage() {
  let workers: Worker[] = []

  try {
    const token = await getBackendToken()
    if (token) workers = await apiGet<Worker[]>('/v1/workers', token)
  } catch { /* backend not running — show empty state */ }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Workers</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Manage deployed AI financial workers</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          {workers.length === 0 ? (
            <div className="bg-brand-surface border border-brand-border rounded-sm p-10 flex items-center justify-center">
              <p className="text-xs font-mono text-brand-muted text-center">
                No workers deployed — deploy your first worker to begin
              </p>
            </div>
          ) : (
            workers.map((worker) => (
              <WorkerCard key={worker.id} worker={worker} />
            ))
          )}
        </div>

        <div className="bg-brand-surface border border-brand-border rounded-sm p-5 space-y-4 h-fit">
          <div>
            <h2 className="font-heading font-semibold text-brand-text text-sm">Deploy Worker</h2>
            <p className="text-[11px] font-mono text-brand-muted mt-0.5">Configure and deploy a new AI worker</p>
          </div>
          <DeployWorkerForm />
        </div>
      </div>
    </div>
  )
}
