'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { WorkerCard } from '@/components/dashboard/workers/WorkerCard'
import type { Worker } from '@/components/dashboard/workers/WorkerCard'
import { ConfigDrawer } from '@/components/dashboard/workers/ConfigDrawer'
import { DeployWorkerForm } from '@/components/dashboard/workers/DeployWorkerForm'

const ALL_WORKER_TYPES = [
  { type: 'invoice_processing', name: 'Invoice Processing Worker', phase: 'MVP', desc: 'Processes invoices end-to-end with policy enforcement and audit trail.' },
  { type: 'ai_accountant', name: 'AI Accountant Worker', phase: 'MVP', desc: 'Categorises bank transactions and matches invoices to payments.' },
  { type: 'receipt_processing', name: 'Receipt Processing Worker', phase: 'MVP', desc: 'Extracts receipt data and validates against expense policy.' },
  { type: 'reconciliation', name: 'Reconciliation Worker', phase: 'V2', desc: 'Matches transactions across multiple sources and flags discrepancies.' },
  { type: 'expense_control', name: 'Expense Control Worker', phase: 'V2', desc: 'Reviews expense claims and enforces company spending policy.' },
  { type: 'fraud_detection', name: 'Fraud Detection Worker', phase: 'V2', desc: 'Monitors transactions and flags suspicious patterns in real time.' },
]

export function WorkersClient({ initialWorkers }: { initialWorkers: Worker[] }) {
  const router = useRouter()
  const [drawerWorker, setDrawerWorker] = useState<Worker | null>(null)
  const [showDeployForm, setShowDeployForm] = useState(false)

  const deployedTypes = new Set(initialWorkers.map((w) => w.type))
  const availableWorkers = ALL_WORKER_TYPES.filter((wt) => !deployedTypes.has(wt.type))

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Workers</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">Manage deployed AI financial workers</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
          Deployed Workers
        </h2>
        {initialWorkers.length === 0 ? (
          <div className="bg-brand-surface border border-brand-border rounded-sm p-10 flex items-center justify-center">
            <p className="text-xs font-mono text-brand-muted text-center">
              No workers deployed — deploy your first worker below
            </p>
          </div>
        ) : (
          initialWorkers.map((worker) => (
            <WorkerCard
              key={worker.id}
              worker={worker}
              onConfigure={() => setDrawerWorker(worker)}
              onStatusChange={() => router.refresh()}
            />
          ))
        )}
      </section>

      {availableWorkers.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
            Available Workers
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {availableWorkers.map((wt) => (
              <div key={wt.type} className="bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-brand-text font-medium">{wt.name}</span>
                    {wt.phase === 'V2' && (
                      <span className="text-[10px] font-mono text-brand-info border border-[rgba(0,168,204,0.2)] bg-[rgba(0,168,204,0.08)] rounded-sm px-1.5 py-0.5">
                        V2
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-mono text-brand-muted mt-0.5">{wt.desc}</p>
                </div>
                {wt.phase === 'MVP' ? (
                  <button
                    type="button"
                    onClick={() => setShowDeployForm(true)}
                    className="self-start bg-brand-green text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-3 py-1.5 text-xs font-mono font-medium transition-all"
                  >
                    Deploy
                  </button>
                ) : (
                  <span className="self-start text-[10px] font-mono text-brand-muted border border-brand-border rounded-sm px-2 py-0.5">
                    Coming Soon
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {showDeployForm && (
        <div className="fixed inset-0 bg-[rgba(0,0,0,0.7)] z-40 flex items-center justify-center p-6">
          <div className="bg-brand-surface border border-brand-border rounded-sm p-6 w-full max-w-sm space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-heading font-semibold text-brand-text text-sm">Deploy Worker</h2>
              <button type="button" onClick={() => setShowDeployForm(false)} className="text-brand-muted hover:text-brand-text text-xs font-mono transition-colors">✕</button>
            </div>
            <DeployWorkerForm />
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
