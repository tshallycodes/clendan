'use client'

interface CloseTask {
  task_key: string
  label: string
  status: 'pending' | 'complete' | 'blocked'
}

interface Props {
  runId: string
  tasks: CloseTask[]
}

export function CloseRunBottlenecks({ tasks }: Props) {
  const bottlenecks = tasks.filter((t) => t.status === 'blocked' || t.status === 'pending')

  if (bottlenecks.length === 0) return null

  return (
    <div className="bg-[rgba(255,77,109,0.08)] border border-[rgba(255,77,109,0.3)] rounded-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-[rgba(255,77,109,0.2)]">
        <p className="text-[11px] font-body uppercase tracking-widest text-[#ff4d6d]">
          Bottlenecks — {bottlenecks.length} task{bottlenecks.length > 1 ? 's' : ''} blocking close
        </p>
      </div>
      <div className="divide-y divide-[rgba(255,77,109,0.15)]">
        {bottlenecks.map((task) => (
          <div key={task.task_key} className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-xs font-body text-brand-text">{task.label}</span>
            <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm ${
              task.status === 'blocked'
                ? 'bg-[rgba(255,77,109,0.12)] text-[#ff4d6d] border border-[rgba(255,77,109,0.3)]'
                : 'bg-[rgba(245,166,35,0.08)] text-[#f5a623] border border-[rgba(245,166,35,0.2)]'
            }`}>
              {task.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
