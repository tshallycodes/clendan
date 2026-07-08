'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import { ToolExecutionsTab } from '@/components/dashboard/tools/ToolExecutionsTab'
import { DocumentsTab } from '@/components/dashboard/tools/DocumentsTab'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import type { ToolDef } from '../tools-data'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { motion, AnimatePresence } from 'framer-motion'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Props {
  tool: ToolDef
  deployed: Tool | null
}

const AUTONOMY_BADGE: Record<string, { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
}

const AUTONOMY_DESC: Record<string, string> = {
  auto:    'Executes automatically - no approval required before acting.',
  approve: 'Every decision is routed to you for review before the agent acts.',
}

const DEFAULT_HOW_IT_WORKS = [
  { step: '01', label: 'Trigger',       desc: 'Tool activates on a schedule or incoming event. Data is pulled from connected integrations.' },
  { step: '02', label: 'Execute',       desc: 'Agent processes the data using your configured rules and AI reasoning.' },
  { step: '03', label: 'Policy check',  desc: 'Every output is validated by the policy engine before any action is taken. Cannot be skipped.' },
  { step: '04', label: 'Audit',         desc: 'Full decision and reasoning trace written to the immutable audit log before returning.' },
]

const pageVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}
const EASE = [0.25, 0.46, 0.45, 0.94] as const
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: EASE } },
}

function DeployPrompt({ tool }: { tool: ToolDef }) {
  const requires = tool.requires.length
    ? tool.requires.map((c) => c.charAt(0).toUpperCase() + c.slice(1)).join(' · ')
    : null
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-16 text-center space-y-2">
      <p className="text-xs font-body text-brand-secondary">This agent is not deployed yet.</p>
      <p className="text-[11px] font-body text-brand-muted">
        Deploy it to start processing and see its activity here.
        {requires && <> Requires a connected {requires} integration.</>}
      </p>
    </div>
  )
}

export function GenericToolClient({ tool, deployed }: Props) {
  const router = useRouter()
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const [showConfig, setShowConfig] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [showOverview, setShowOverview] = useState(false)

  const isActive = deployed?.status === 'active'
  const isDoc = tool.type === 'document_intelligence'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.approve) : null

  async function handleToggle() {
    if (!deployed) return
    setToggling(true)
    try {
      const token = await getToken()
      await fetch(`${API}/tools/${deployed.id}/pause`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      router.refresh()
    } finally {
      setToggling(false)
    }
  }

  async function handleDeploy() {
    setDeploying(true)
    try {
      const token = await getToken()
      if (deployed) {
        await fetch(`${API}/tools/${deployed.id}/pause`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        })
      } else {
        const { getDefaultConfig } = await import('@/components/dashboard/tools/ToolConfigFields')
        await fetch(`${API}/tools`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: tool.type, autonomy_level: 'approve', config: getDefaultConfig(tool.type) }),
        })
      }
      router.refresh()
    } finally {
      setDeploying(false)
    }
  }

  const actionLoading = toggling || deploying

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="p-6 space-y-6">
      <motion.div variants={sectionVariants}>
        <Link href="/tools" className="text-[12px] font-body text-brand-muted hover:text-brand-secondary transition-colors">
          &larr; Tools
        </Link>
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-heading font-bold text-2xl text-brand-text">{tool.name}</h1>
            {badge && !isDoc && <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>}
          </div>
          <p className="text-xs font-body text-brand-muted max-w-xl">{tool.desc}</p>
        </div>

        {canConfigure && (
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setShowOverview(true)}
              className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors">
              Overview
            </button>
            <button type="button" onClick={() => setShowConfig(true)}
              className="text-xs font-body border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-3 py-1.5 transition-colors">
              Configure
            </button>
            <button type="button" onClick={isActive ? handleToggle : handleDeploy} disabled={actionLoading}
              className={`text-xs font-body rounded-sm px-3 py-1.5 transition-all disabled:opacity-50 ${
                isActive
                  ? 'border border-brand-border text-brand-text hover:bg-brand-elevated'
                  : 'bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97]'
              }`}>
              {toggling ? 'Pausing…' : deploying ? 'Deploying…' : isActive ? 'Pause' : 'Deploy'}
            </button>
          </div>
        )}
      </motion.div>

      <motion.div variants={sectionVariants} className="flex items-center gap-2">
        {isActive ? (
          <>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-60" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00C853]" />
            </span>
            <span className="text-xs font-body text-[#00C853]">Active</span>
          </>
        ) : (
          <>
            <span className="h-2 w-2 rounded-full bg-brand-muted" />
            <span className="text-xs font-body text-brand-muted">{deployed ? 'Paused' : 'Not deployed'}</span>
          </>
        )}
      </motion.div>

      {/* Main body - the tool's working surface (documents for doc-intel, run activity otherwise). */}
      <motion.div variants={sectionVariants}>
        {isDoc ? (
          <DocumentsTab toolId={deployed?.id ?? null} />
        ) : deployed ? (
          <ToolExecutionsTab toolId={deployed.id} />
        ) : (
          <DeployPrompt tool={tool} />
        )}
      </motion.div>

      {/* Overview Sidebar */}
      <AnimatePresence>
        {showOverview && (
          <div className="fixed inset-0 z-40 flex justify-end">
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
              className="absolute inset-0 bg-black/40" onClick={() => setShowOverview(false)}
            />
            <motion.div
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="relative h-screen w-[400px] bg-brand-surface border-l border-brand-border p-6 overflow-y-auto shadow-2xl z-50 flex flex-col"
            >
              <div className="flex items-center justify-between mb-6 shrink-0">
                <h2 className="font-heading font-semibold text-brand-text text-sm">Overview</h2>
                <button type="button" onClick={() => setShowOverview(false)} className="text-brand-muted hover:text-brand-text transition-colors text-lg leading-none">✕</button>
              </div>

              <div className="space-y-6 flex-1">
                {/* Required integrations */}
                <div className="bg-brand-bg border border-brand-border rounded-sm px-4 py-3">
                  <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Requires</p>
                  <p className="text-xs font-body text-brand-secondary mt-1">
                    {tool.requires.length
                      ? tool.requires.map((c) => c.charAt(0).toUpperCase() + c.slice(1)).join(' · ')
                      : 'No integration - runs on upload or manual trigger'}
                  </p>
                </div>

                {/* How it works */}
                <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">How it works</p>
                    <p className="text-[11px] font-body text-brand-muted mt-0.5">
                      {tool.howItWorks
                        ? 'Every upload follows this fixed processing flow - no step can be skipped'
                        : 'Every run follows this fixed execution flow - no step can be skipped'}
                    </p>
                  </div>
                  <div className="grid grid-cols-1 divide-y divide-brand-border">
                    {(tool.howItWorks ?? DEFAULT_HOW_IT_WORKS).map(({ step, label, desc }) => (
                      <div key={step} className="px-4 py-3 space-y-1.5 flex gap-4">
                        <p className="text-[11px] font-body text-brand-muted font-mono">{step}</p>
                        <div>
                          <p className="text-xs font-body font-medium text-brand-text">{label}</p>
                          <p className="text-[11px] font-body text-brand-muted leading-relaxed mt-0.5">{desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Configuration */}
                {deployed && (
                  <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                    <div className="px-4 py-3 border-b border-brand-border">
                      <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Configuration</p>
                    </div>
                    <div className="px-4 py-4 space-y-4">
                      {!isDoc && (
                        <div className="space-y-1.5">
                          <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Autonomy</p>
                          {badge && <span className={`text-[11px] font-body px-2 py-0.5 rounded-sm inline-block ${badge.className}`}>{badge.label}</span>}
                          <p className="text-[11px] font-body text-brand-muted leading-relaxed">{AUTONOMY_DESC[deployed.autonomy_level] ?? ''}</p>
                        </div>
                      )}
                      <div className="space-y-1.5">
                        <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Status</p>
                        <p className="text-xs font-body text-brand-text">{deployed.status === 'active' ? 'Running' : 'Paused'}</p>
                        <p className="text-[11px] font-body text-brand-muted">{deployed.status === 'active' ? 'Agent is live and processing' : 'Agent is paused - no runs will fire'}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Capabilities */}
                <div className="bg-brand-bg border border-brand-border rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-brand-border">
                    <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Capabilities</p>
                    <p className="text-[11px] font-body text-brand-muted mt-0.5">What this agent does once deployed and connected to your data</p>
                  </div>
                  {tool.capabilities.length > 0
                    ? <ul className="divide-y divide-brand-border">
                        {tool.capabilities.map(cap => (
                          <li key={cap} className="flex items-start gap-3 px-4 py-3">
                            <span className="text-brand-muted font-body text-[11px] mt-0.5 shrink-0">→</span>
                            <span className="text-xs font-body text-brand-secondary">{cap}</span>
                          </li>
                        ))}
                      </ul>
                    : <p className="px-4 py-8 text-xs font-body text-brand-muted text-center">No capabilities listed.</p>
                  }
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {showConfig && (
        <ConfigDrawer
          tool={deployed}
          toolType={tool.type}
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); router.refresh() }}
        />
      )}
    </motion.div>
  )
}
