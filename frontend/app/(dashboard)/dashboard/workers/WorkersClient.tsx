'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { WorkerCard } from '@/components/dashboard/workers/WorkerCard'
import type { Worker } from '@/components/dashboard/workers/WorkerCard'
import { ConfigDrawer } from '@/components/dashboard/workers/ConfigDrawer'
import { DeployWorkerForm } from '@/components/dashboard/workers/DeployWorkerForm'
import { useCanConfigure } from '@/lib/auth-client'

export function WorkersClient({ initialWorkers }: { initialWorkers: Worker[] }) {
  const router = useRouter()
  const canConfigure = useCanConfigure()
  const [drawerWorker, setDrawerWorker] = useState<Worker | null>(null)
  const [showDeployForm, setShowDeployForm] = useState(false)

  return (
    <div className="p-6 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Workers</h1>
          <p className="text-brand-muted text-xs font-mono mt-1">Manage deployed AI financial workers</p>
        </div>
        {canConfigure && (
          <button
            type="button"
            onClick={() => setShowDeployForm(true)}
            className="bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-mono font-medium transition-all"
          >
            Deploy Worker
          </button>
        )}
      </div>

      {initialWorkers.length === 0 ? (
        <div className="bg-brand-surface border border-brand-border rounded-sm p-16 flex flex-col items-center justify-center gap-4">
          <p className="text-xs font-mono text-brand-muted">No workers deployed yet</p>
          {canConfigure && (
            <button
              type="button"
              onClick={() => setShowDeployForm(true)}
              className="bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2 text-xs font-mono font-medium transition-all"
            >
              Deploy your first worker
            </button>
          )}
        </div>
      ) : (
        <section className="space-y-3">
          {initialWorkers.map((worker) => (
            <WorkerCard
              key={worker.id}
              worker={worker}
              onConfigure={() => setDrawerWorker(worker)}
              onStatusChange={() => router.refresh()}
            />
          ))}
        </section>
      )}

      {showDeployForm && (
        <div className="fixed inset-0 bg-[rgba(0,0,0,0.7)] z-40 flex items-start justify-center p-6 overflow-y-auto">
          <div className="bg-brand-surface border border-brand-border rounded-sm w-full max-w-sm my-auto">
            <div className="sticky top-0 bg-brand-surface border-b border-brand-border flex items-center justify-between px-6 py-4 z-10">
              <h2 className="font-heading font-semibold text-brand-text text-sm">Deploy Worker</h2>
              <button type="button" onClick={() => setShowDeployForm(false)} className="text-brand-muted hover:text-brand-text text-xs font-mono transition-colors">✕</button>
            </div>
            <div className="p-6">
              <DeployWorkerForm onDeployed={() => { setShowDeployForm(false); router.refresh() }} />
            </div>
          </div>
        </div>
      )}

      {drawerWorker && (
        <ConfigDrawer
          worker={drawerWorker}
          onClose={() => setDrawerWorker(null)}
          onSaved={() => { setDrawerWorker(null); router.refresh() }}
        />
      )}
    </div>
  )
}
