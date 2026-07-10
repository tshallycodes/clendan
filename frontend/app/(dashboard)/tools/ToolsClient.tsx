'use client'

import { Fragment, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowRight } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { useToast } from '@/components/Providers'
import { WORKFLOWS, toolsForWorkflow, TOOLS, INTEGRATION_CATEGORY_LABELS, type ToolDef } from './tools-data'
import type { Tool } from '@/components/dashboard/tools/ToolCard'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface WorkflowConnection {
  from_type: string
  to_type: string
  enabled: boolean
  // Records processed upstream but not yet handled downstream (null for window-based edges).
  backlog?: number | null
  downstream_tool_id?: string | null
  downstream_active?: boolean
}

interface Props {
  deployedTools: Tool[]
  connections: WorkflowConnection[]
}

const pageVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}
const gridVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const cardVariants = {
  hidden: { opacity: 0, y: 16, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] as const } },
}

const edgeKey = (from: string, to: string) => `${from}->${to}`

function ToolCard({ tool, deployed, step }: { tool: ToolDef; deployed: Tool | undefined; step: number }) {
  const isActive = deployed?.status === 'active'
  const isInactive = deployed && !isActive

  return (
    <motion.div variants={cardVariants} className="w-full lg:flex-1 min-w-0 flex">
      <Link
        href={`/tools/${tool.slug}`}
        className="group bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3 hover:bg-brand-elevated transition-colors w-full"
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

        <div className="flex items-baseline gap-1.5">
          <span className="text-[11px] font-body text-brand-muted shrink-0">Requires:</span>
          <span className="text-[11px] font-body text-brand-secondary">
            {tool.requires.length
              ? tool.requires.map((c) => INTEGRATION_CATEGORY_LABELS[c]).join(' · ')
              : 'Upload only - no integration'}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[11px] font-body text-brand-muted">{tool.capabilities.length} capabilities</span>
          <span className="flex items-center gap-1 text-[11px] font-body text-brand-muted group-hover:text-brand-secondary transition-colors">
            {deployed ? 'Configure' : 'Deploy'} <ArrowRight className="w-3 h-3" />
          </span>
        </div>
      </Link>
    </motion.div>
  )
}

function Connector({
  enabled, pending, onToggle, backlog, downstreamActive, downstreamName, flushing, onFlush,
}: {
  enabled: boolean; pending: boolean; onToggle: () => void
  backlog: number | null | undefined; downstreamActive: boolean; downstreamName: string
  flushing: boolean; onFlush: () => void
}) {
  const waiting = typeof backlog === 'number' && backlog > 0
  return (
    <div className="shrink-0 self-center flex flex-col items-center gap-1 px-1 lg:px-2.5 py-2 lg:py-0">
      {/* The arrow IS the toggle: on = along the flow (→ desktop, ↓ mobile), off = off-axis + dimmed. */}
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={enabled ? 'Connected - click to disconnect auto-handoff' : 'Disconnected - click to connect auto-handoff'}
        title={enabled ? 'Connected - a successful run auto-triggers the next tool' : 'Disconnected - tools run independently'}
        onClick={onToggle}
        disabled={pending}
        className="group flex items-center justify-center disabled:opacity-50 active:scale-90 transition-transform"
      >
        <ArrowRight
          weight="bold"
          className={`w-5 h-5 transition-all duration-200 group-hover:text-brand-text ${
            enabled ? 'rotate-90 lg:rotate-0 text-brand-secondary' : 'rotate-0 lg:rotate-90 text-brand-muted opacity-40'
          }`}
        />
      </button>

      {/* Backlog: records processed upstream but not yet handled downstream - flush manually. */}
      {waiting && (
        <>
          <span
            className="text-[10px] font-body text-[#f5a623] whitespace-nowrap tabular-nums"
            title={`${backlog} record(s) processed but not yet sent to ${downstreamName}`}
          >
            {backlog} waiting
          </span>
          {downstreamActive ? (
            <button
              type="button"
              onClick={onFlush}
              disabled={flushing}
              title={`Run ${downstreamName} now to process the ${backlog} waiting record(s)`}
              className="text-[10px] font-body px-2 py-0.5 rounded-sm border border-brand-border text-brand-text hover:bg-brand-elevated whitespace-nowrap disabled:opacity-50 active:scale-95 transition-all"
            >
              {flushing ? 'Sending…' : `Run ${downstreamName}`}
            </button>
          ) : (
            <span className="text-[10px] font-body text-brand-muted whitespace-nowrap">deploy to flush</span>
          )}
        </>
      )}
    </div>
  )
}

export function ToolsClient({ deployedTools, connections }: Props) {
  const { getToken } = useAuth()
  const { toast } = useToast()

  // One record per tool type - prefer an active deployment if the backend returns several.
  const deployedByType = new Map<string, Tool>()
  for (const d of deployedTools) {
    const existing = deployedByType.get(d.type)
    if (!existing || (d.status === 'active' && existing.status !== 'active')) {
      deployedByType.set(d.type, d)
    }
  }
  const totalDeployed = TOOLS.filter((t) => deployedByType.get(t.type)?.status === 'active').length

  const [conns, setConns] = useState<WorkflowConnection[]>(connections)
  const [pendingEdge, setPendingEdge] = useState<string | null>(null)
  const [flushingEdge, setFlushingEdge] = useState<string | null>(null)

  const byEdge = useMemo(() => {
    const m: Record<string, WorkflowConnection> = {}
    for (const c of conns) m[edgeKey(c.from_type, c.to_type)] = c
    return m
  }, [conns])
  const connFor = (from: string, to: string): WorkflowConnection | undefined => byEdge[edgeKey(from, to)]
  const isEnabled = (from: string, to: string) => connFor(from, to)?.enabled ?? true

  async function refetchConnections() {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/workflows/connections`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) { const j = await res.json(); setConns(j.data?.connections ?? []) }
    } catch { /* keep the last known state */ }
  }

  async function toggleConnection(from: string, to: string) {
    const key = edgeKey(from, to)
    const current = isEnabled(from, to)
    const next = !current
    setConns((cs) => cs.map((c) => (c.from_type === from && c.to_type === to ? { ...c, enabled: next } : c)))
    setPendingEdge(key)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/workflows/connections`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_type: from, to_type: to, enabled: next }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const fromName = TOOLS.find((t) => t.type === from)?.name ?? 'Upstream'
      const toName = TOOLS.find((t) => t.type === to)?.name ?? 'the next tool'
      toast(
        next
          ? `Connected - ${fromName} will auto-run ${toName}`
          : `Disconnected - ${fromName} and ${toName} run independently`,
        'success',
      )
    } catch {
      setConns((cs) => cs.map((c) => (c.from_type === from && c.to_type === to ? { ...c, enabled: current } : c))) // revert
      toast('Could not update connection', 'error')
    } finally {
      setPendingEdge(null)
    }
  }

  async function flushConnection(from: string, to: string) {
    const conn = connFor(from, to)
    if (!conn?.downstream_tool_id) return
    const key = edgeKey(from, to)
    setFlushingEdge(key)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/tools/${conn.downstream_tool_id}/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: {} }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const toName = TOOLS.find((t) => t.type === to)?.name ?? 'the next tool'
      toast(`Sent ${conn.backlog ?? ''} to ${toName} - assessing now`.replace('  ', ' '), 'success')
      // The downstream job runs async; give it a moment, then refresh the backlog counts.
      setTimeout(() => { void refetchConnections() }, 2500)
    } catch {
      toast('Could not run the downstream tool', 'error')
    } finally {
      setFlushingEdge(null)
    }
  }

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-10">
      <motion.div variants={sectionVariants}>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Tools</h1>
        <p className="text-xs font-body text-brand-muted mt-1 leading-relaxed max-w-xl">
          Autonomous AI agents grouped by the two workflows they run end-to-end: accounts payable feeds month-end close. Toggle the connection between two tools to control whether a successful run automatically hands off to the next.
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

            <motion.div variants={gridVariants} className="flex flex-col lg:flex-row lg:items-stretch">
              {tools.map((tool, i) => {
                const next = tools[i + 1]
                return (
                  <Fragment key={tool.slug}>
                    <ToolCard tool={tool} step={i + 1} deployed={deployedByType.get(tool.type)} />
                    {next && (
                      <Connector
                        enabled={isEnabled(tool.type, next.type)}
                        pending={pendingEdge === edgeKey(tool.type, next.type)}
                        onToggle={() => toggleConnection(tool.type, next.type)}
                        backlog={connFor(tool.type, next.type)?.backlog}
                        downstreamActive={connFor(tool.type, next.type)?.downstream_active ?? false}
                        downstreamName={next.name}
                        flushing={flushingEdge === edgeKey(tool.type, next.type)}
                        onFlush={() => flushConnection(tool.type, next.type)}
                      />
                    )}
                  </Fragment>
                )
              })}
            </motion.div>
          </motion.section>
        )
      })}
    </motion.div>
  )
}
