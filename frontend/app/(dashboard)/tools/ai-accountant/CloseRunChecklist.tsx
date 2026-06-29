'use client'

const MANUAL_TASKS = new Set(['payroll_reconciled', 'sign_offs_collected'])

const TASK_DESCRIPTIONS: Record<string, string> = {
  all_transactions_categorised: 'Checked automatically — passes when no pending or uncategorised transactions remain for this period.',
  reconciliation_complete:      'Checked automatically — passes when a completed reconciliation run exists for this period.',
  approvals_resolved:           'Checked automatically — passes when there are no pending approvals awaiting a decision.',
  payroll_reconciled:           'Confirm manually once payroll for this period has been processed and verified against your records.',
  sign_offs_collected:          'Confirm manually once the appropriate team members have reviewed and approved the period\'s financials.',
}

interface CloseTask {
  task_key: string
  label: string
  status: 'pending' | 'complete' | 'blocked'
  completed_at: string | null
  completed_by: string | null
  notes: string | null
}

interface Props {
  tasks: CloseTask[]
  onCompleteTask: (taskKey: string) => void
  runClosed: boolean
}

const STATUS_ICON: Record<string, { icon: string; cls: string }> = {
  complete: { icon: '✓', cls: 'text-[#00C853]' },
  pending:  { icon: '○', cls: 'text-[#f5a623]' },
  blocked:  { icon: '✕', cls: 'text-[#ff4d6d]' },
}

const STATUS_BADGE_CLS: Record<string, string> = {
  complete: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]',
  pending:  'bg-[rgba(245,166,35,0.08)] text-[#f5a623] border border-[rgba(245,166,35,0.2)]',
  blocked:  'bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]',
}

export function CloseRunChecklist({ tasks, onCompleteTask, runClosed }: Props) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-brand-border">
        <p className="text-[10px] font-mono uppercase tracking-widest text-brand-muted">Checklist</p>
      </div>
      <div className="divide-y divide-brand-border">
        {tasks.map((task) => {
          const { icon, cls } = STATUS_ICON[task.status] ?? STATUS_ICON.pending
          const isManual = MANUAL_TASKS.has(task.task_key)
          const canComplete = isManual && task.status !== 'complete' && !runClosed

          return (
            <div key={task.task_key} className="px-4 py-3 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <span className={`text-sm font-mono shrink-0 ${cls}`}>{icon}</span>
                <div className="min-w-0">
                  <p className="text-xs font-mono text-brand-text truncate">{task.label}</p>
                  <p className="text-[10px] font-mono text-brand-muted mt-0.5 leading-relaxed">
                    {TASK_DESCRIPTIONS[task.task_key]}
                  </p>
                  {task.completed_by && (
                    <p className="text-[10px] font-mono text-brand-muted mt-0.5">
                      by {task.completed_by}
                    </p>
                  )}
                  {task.notes && (
                    <p className="text-[10px] font-mono text-brand-muted mt-0.5 truncate">{task.notes}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${STATUS_BADGE_CLS[task.status] ?? ''}`}>
                  {task.status}
                </span>
                {canComplete && (
                  <button
                    type="button"
                    onClick={() => onCompleteTask(task.task_key)}
                    className="text-[10px] font-mono border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-2 py-0.5 transition-colors"
                  >
                    Mark Complete
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
