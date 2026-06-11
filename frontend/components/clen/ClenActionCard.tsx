'use client'

import { motion } from 'framer-motion'

interface Action {
  tool: string
  description: string
  params: Record<string, unknown>
}

interface Props {
  action: Action
  onConfirm: () => void
  onCancel: () => void
}

export function ClenActionCard({ action, onConfirm, onCancel }: Props) {
  const paramEntries = Object.entries(action.params).slice(0, 4)

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className="my-2 border border-brand-border rounded-sm bg-brand-surface overflow-hidden"
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-brand-border bg-brand-bg">
        <span className="text-brand-warning text-xs">⚡</span>
        <span className="text-[10px] font-mono text-brand-secondary uppercase tracking-wider">
          About to execute
        </span>
        <span className="ml-auto text-[10px] font-mono text-brand-muted">{action.tool}</span>
      </div>

      <div className="px-3 py-2">
        <p className="text-xs font-mono text-brand-text mb-2">{action.description}</p>

        {paramEntries.length > 0 && (
          <div className="space-y-1 mb-3">
            {paramEntries.map(([key, val]) => (
              <div key={key} className="flex gap-2 text-[10px] font-mono">
                <span className="text-brand-muted shrink-0">{key}</span>
                <span className="text-brand-secondary truncate">
                  {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={onConfirm}
            className="flex-1 h-7 text-[11px] font-mono font-medium rounded-sm bg-brand-green text-black hover:bg-[#00a844] transition-colors active:scale-[0.97]"
          >
            Confirm
          </button>
          <button
            onClick={onCancel}
            className="flex-1 h-7 text-[11px] font-mono text-brand-secondary border border-brand-border rounded-sm hover:bg-brand-elevated transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </motion.div>
  )
}
