'use client'

import Link from 'next/link'
import { ArrowRight } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { WORKFLOWS, toolsForWorkflow, TOOLS, type ToolDef } from './tools-data'
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

function ToolCard({ tool, deployed, step }: { tool: ToolDef; deployed: Tool | undefined; step: number }) {
  const isActive = deployed?.status === 'active'
  const isInactive = deployed && !isActive

  return (
    <motion.div variants={cardVariants} className="h-full">
      <Link
        href={`/tools/${tool.slug}`}
        className={`group bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3 hover:bg-brand-elevated transition-colors h-full ${
          isActive ? 'border-l-[3px] border-l-[#00C853]' : isInactive ? 'border-l-[3px] border-l-brand-border' : ''
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2.5 min-w-0">
            <span className="text-[11px] font-body text-brand-muted tabular-nums leading-tight pt-0.5 shrink-0">
              {String(step).padStart(2, '0')}
            </span>
            <p className="text-sm font-body font-medium text-brand-text group-hover:text-[#00C853] transition-colors leading-tight">
              {tool.name}
            </p>
          </div>
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
  // One record per tool type — prefer an active deployment if the backend returns several.
  const deployedByType = new Map<string, Tool>()
  for (const d of deployedTools) {
    const existing = deployedByType.get(d.type)
    if (!existing || (d.status === 'active' && existing.status !== 'active')) {
      deployedByType.set(d.type, d)
    }
  }
  const totalDeployed = TOOLS.filter((t) => deployedByType.get(t.type)?.status === 'active').length

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-10">
      <motion.div variants={sectionVariants}>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Tools</h1>
        <p className="text-xs font-body text-brand-muted mt-1 leading-relaxed max-w-xl">
          Autonomous AI agents grouped by the two workflows they run end-to-end: accounts payable feeds month-end close. Each tool runs independently, routes decisions through the policy engine, and writes a full audit trail before taking any action.
        </p>
        <p className="text-[11px] font-body text-brand-muted mt-2">
          {totalDeployed} of {TOOLS.length} deployed across {WORKFLOWS.length} workflows
        </p>
      </motion.div>

      {WORKFLOWS.map((workflow, wi) => {
        const tools = toolsForWorkflow(workflow)
        const activeCount = tools.filter((t) => deployedByType.get(t.type)?.status === 'active').length

        return (
          <motion.section key={workflow.id} variants={sectionVariants} className="space-y-4">
            <div className="flex items-end justify-between gap-4 border-b border-brand-border pb-3">
              <div className="min-w-0">
                <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">
                  Workflow {String(wi + 1).padStart(2, '0')} · {workflow.name}
                </p>
                <h2 className="font-heading font-bold text-lg text-brand-text mt-1.5">{workflow.headline}</h2>
                <p className="text-xs font-body text-brand-muted mt-1 leading-relaxed max-w-2xl">{workflow.tagline}</p>
              </div>
              <span className="text-[11px] font-body text-brand-muted whitespace-nowrap shrink-0">
                {activeCount} / {tools.length} active
              </span>
            </div>

            <motion.div variants={gridVariants} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {tools.map((tool, i) => (
                <ToolCard
                  key={tool.slug}
                  tool={tool}
                  step={i + 1}
                  deployed={deployedByType.get(tool.type)}
                />
              ))}
            </motion.div>
          </motion.section>
        )
      })}
    </motion.div>
  )
}
