'use client'

import Link from 'next/link'
import { ArrowRight } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { TOOLS, type ToolDef } from './tools-data'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

interface Props {
  deployedTools: Tool[]
}

const pageVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}
const gridVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
const cardVariants = {
  hidden: { opacity: 0, y: 16, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}

function ToolCard({ tool, deployed }: { tool: ToolDef; deployed: Tool | undefined }) {
  const isActive = deployed?.status === 'active'
  const isInactive = deployed && !isActive

  return (
    <motion.div variants={cardVariants}>
      <Link
        href={`/tools/${tool.slug}`}
        className={`group bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3 hover:bg-brand-elevated transition-colors h-full ${
          isActive ? 'border-l-[3px] border-l-[#00C853]' : isInactive ? 'border-l-[3px] border-l-brand-border' : ''
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-body font-medium text-brand-text group-hover:text-[#00C853] transition-colors leading-tight">
            {tool.name}
          </p>
          {isActive ? (
            <span className="text-[11px] font-body px-2 py-0.5 rounded-sm shrink-0 bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]">
              Active
            </span>
          ) : isInactive ? (
            <span className="text-[11px] font-body px-2 py-0.5 rounded-sm shrink-0 bg-brand-elevated text-brand-muted border border-brand-border">
              Inactive
            </span>
          ) : null}
        </div>

        <p className="text-[12px] font-body text-brand-muted leading-relaxed flex-1">{tool.desc}</p>

        <div className="flex items-center justify-between">
          <span className="text-[11px] font-body text-brand-muted">
            {tool.capabilities.length} capabilities
          </span>
          <span className="flex items-center gap-1 text-[11px] font-body text-brand-muted group-hover:text-brand-secondary transition-colors">
            {deployed ? 'Configure' : 'Deploy'} <ArrowRight className="w-3 h-3" />
          </span>
        </div>
      </Link>
    </motion.div>
  )
}

export function ToolsClient({ deployedTools }: Props) {
  const activeTools = TOOLS.filter((t) => deployedTools.find((d) => d.type === t.type && d.status === 'active'))
  const availableTools = TOOLS.filter((t) => !deployedTools.find((d) => d.type === t.type && d.status === 'active'))
  const deployedCount = deployedTools.filter((t) => t.status === 'active').length

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-8">
      <motion.div variants={sectionVariants}>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Tools</h1>
        <p className="text-xs font-body text-brand-muted mt-1 leading-relaxed max-w-xl">
          Autonomous AI agents that connect to your financial systems, execute tasks, enforce policy, and produce full audit trails. Each tool runs independently and routes decisions through the policy engine before taking any action.
        </p>
        <p className="text-[11px] font-body text-brand-muted mt-2">
          {deployedCount} of {TOOLS.length} deployed
        </p>
      </motion.div>

      {activeTools.length > 0 && (
        <motion.div variants={sectionVariants} className="space-y-3">
          <div>
            <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Deployed</p>
            <p className="text-[11px] font-body text-brand-muted mt-0.5">Running on your financial data — click to configure or view executions</p>
          </div>
          <motion.div variants={gridVariants} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {activeTools.map((tool) => (
              <ToolCard key={tool.slug} tool={tool} deployed={deployedTools.find((d) => d.type === tool.type)} />
            ))}
          </motion.div>
        </motion.div>
      )}

      <motion.div variants={sectionVariants} className="space-y-3">
        <div>
          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">
            {activeTools.length > 0 ? 'Available to Deploy' : 'All Tools'}
          </p>
          <p className="text-[11px] font-body text-brand-muted mt-0.5">
            {activeTools.length > 0
              ? 'Connect your integrations and deploy additional agents to your workflow'
              : 'Deploy an agent to start automating — each tool connects to your accounting software and bank accounts'}
          </p>
        </div>
        <motion.div variants={gridVariants} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {availableTools.map((tool) => (
            <ToolCard key={tool.slug} tool={tool} deployed={deployedTools.find((d) => d.type === tool.type)} />
          ))}
        </motion.div>
      </motion.div>
    </motion.div>
  )
}
