'use client'

import { motion } from 'framer-motion'

const listVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
}

const rowVariants = {
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] } },
}

interface DeployedTool {
  id: string
  type: string
  autonomy_level: string
  status: string
  version: number
}

const TOOL_NAMES: Record<string, string> = {
  document_intelligence: 'Document Intelligence',
  ai_accountant: 'AI Accountant',
  spend_control: 'Spend Control',
  ar_collections: 'AR & Collections',
  risk_compliance: 'Risk & Compliance',
  treasury_cash: 'Treasury & Cash',
  reconciliation: 'Reconciliation',
  revenue_recognition: 'Revenue Recognition',
  credit_underwriting: 'Credit Underwriting',
  tax_compliance: 'Tax Compliance',
}

const AUTONOMY_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  auto:    { bg: 'bg-[rgba(0,200,83,0.08)]',  text: 'text-[#00C853]', border: 'border-[rgba(0,200,83,0.2)]',  label: 'AUTO' },
  approve: { bg: 'bg-[rgba(0,168,204,0.08)]', text: 'text-[#00a8cc]', border: 'border-[rgba(0,168,204,0.2)]', label: 'APPROVE' },
  suggest: { bg: 'bg-[rgba(245,166,35,0.08)]',text: 'text-[#f5a623]', border: 'border-[rgba(245,166,35,0.2)]',label: 'SUGGEST' },
}

function toolDisplayName(type: string): string {
  return TOOL_NAMES[type] ?? type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

export function ToolsList({ tools }: { tools: DeployedTool[] }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-brand-border">
        <h2 className="font-heading font-semibold text-brand-text text-sm">Active Tools</h2>
      </div>
      {tools.length === 0 ? (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="px-5 py-8 text-xs font-mono text-brand-muted text-center"
        >
          No tools deployed yet — deploy your first tool to get started
        </motion.p>
      ) : (
        <motion.div variants={listVariants} initial="hidden" animate="show" className="divide-y divide-brand-border">
          {tools.map((tool) => {
            const isActive = tool.status === 'active'
            const autonomy = AUTONOMY_STYLES[tool.autonomy_level] ?? AUTONOMY_STYLES.suggest
            return (
              <motion.div key={tool.id} variants={rowVariants} className="px-5 py-3 flex items-center gap-4 hover:bg-brand-elevated transition-colors">
                <span className="relative flex h-2.5 w-2.5 shrink-0">
                  {isActive && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-60" />
                  )}
                  <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isActive ? 'bg-[#00C853]' : 'bg-brand-muted'}`} />
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono text-brand-text truncate">{toolDisplayName(tool.type)}</div>
                  <div className="text-[10px] font-mono text-brand-muted">{tool.type}</div>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border shrink-0 ${autonomy.bg} ${autonomy.text} ${autonomy.border}`}>
                  {autonomy.label}
                </span>
                <span className="text-[10px] font-mono text-brand-muted shrink-0">v{tool.version}</span>
              </motion.div>
            )
          })}
        </motion.div>
      )}
    </div>
  )
}
