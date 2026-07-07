'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import { ToolExecutionsTab } from '@/components/dashboard/tools/ToolExecutionsTab'
import { ToolApprovalsTab } from '@/components/dashboard/tools/ToolApprovalsTab'
import { ToolAuditTab } from '@/components/dashboard/tools/ToolAuditTab'
import { DocumentsTab } from '@/components/dashboard/tools/DocumentsTab'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import { INTEGRATION_CATEGORY_LABELS, type ToolDef } from '../tools-data'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'
import { motion } from 'framer-motion'

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
  auto:    'Executes automatically — no approval required before acting.',
  approve: 'Every decision is routed to you for review before the agent acts.',
}

const DEFAULT_HOW_IT_WORKS = [
  { step: '01', label: 'Trigger',       desc: 'Tool activates on a schedule or incoming event. Data is pulled from connected integrations.' },
  { step: '02', label: 'Execute',       desc: 'Agent processes the data using your configured rules and AI reasoning.' },
  { step: '03', label: 'Policy check',  desc: 'Every output is validated by the policy engine before any action is taken. Cannot be skipped.' },
  { step: '04', label: 'Audit',         desc: 'Full decision and reasoning trace written to the immutable audit log before returning.' },
]

const pageVariants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
const EASE = [0.25, 0.46, 0.45, 0.94] as const
const sectionVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: EASE } },
}

type TabKey = 'documents' | 'overview' | 'executions' | 'approvals' | 'audit'

function SectionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-brand-border">
        <p className="text-[11px] font-body uppercase tracking-widest text-brand-muted">{title}</p>
        {subtitle && <p className="text-[11px] font-body text-brand-muted mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

function OverviewPanel({ tool, deployed }: { tool: ToolDef; deployed: Tool | null }) {
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.approve) : null
  const isDoc = tool.type === 'document_intelligence'

  return (
    <div className="space-y-4">
      <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-3 flex items-baseline gap-2 flex-wrap">
        <span className="text-[11px] font-body uppercase tracking-widest text-brand-muted">Requires</span>
        <span className="text-xs font-body text-brand-secondary">
          {tool.requires.length
            ? tool.requires.map((c) => INTEGRATION_CATEGORY_LABELS[c]).join(' · ')
            : 'No integration — runs on upload or manual trigger'}
        </span>
        <Link href="/integrations" className="text-[11px] font-body text-brand-muted hover:text-brand-secondary transition-colors ml-auto">
          Manage integrations &rarr;
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <SectionCard
          title="How it works"
          subtitle={tool.howItWorks ? 'Every upload follows this fixed flow — no step can be skipped' : 'Every run follows this fixed flow — no step can be skipped'}
        >
          <div className="divide-y divide-brand-border">
            {(tool.howItWorks ?? DEFAULT_HOW_IT_WORKS).map(({ step, label, desc }) => (
              <div key={step} className="px-4 py-3 flex gap-4">
                <p className="text-[11px] font-body text-brand-muted">{step}</p>
                <div>
                  <p className="text-xs font-body font-medium text-brand-text">{label}</p>
                  <p className="text-[11px] font-body text-brand-muted leading-relaxed mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Capabilities" subtitle="What this agent does once deployed and connected to your data">
          {tool.capabilities.length > 0 ? (
            <ul className="divide-y divide-brand-border">
              {tool.capabilities.map((cap) => (
                <li key={cap} className="flex items-start gap-3 px-4 py-3">
                  <span className="text-brand-muted font-body text-[11px] mt-0.5 shrink-0">&rarr;</span>
                  <span className="text-xs font-body text-brand-secondary">{cap}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-4 py-8 text-xs font-body text-brand-muted text-center">No capabilities listed.</p>
          )}
        </SectionCard>
      </div>

      {deployed && (
        <SectionCard title="Configuration">
          <div className="px-4 py-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
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
              <p className="text-[11px] font-body text-brand-muted">
                {deployed.status === 'active' ? 'Agent is live and processing' : 'Agent is paused — no runs will fire'}
              </p>
            </div>
          </div>
        </SectionCard>
      )}
    </div>
  )
}

function DeployPrompt({ label }: { label: string }) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm px-4 py-12 text-center">
      <p className="text-xs font-body text-brand-muted">Deploy this tool to start seeing {label}.</p>
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

  const isActive = deployed?.status === 'active'
  const isDoc = tool.type === 'document_intelligence'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.approve) : null

  const TABS: { key: TabKey; label: string }[] = [
    ...(isDoc ? [{ key: 'documents' as const, label: 'Documents' }] : []),
    { key: 'overview', label: 'Overview' },
    { key: 'executions', label: 'Executions' },
    { key: 'approvals', label: 'Approvals' },
    { key: 'audit', label: 'Audit' },
  ]
  const [tab, setTab] = useState<TabKey>(isDoc ? 'documents' : 'overview')

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

      {/* Tab nav */}
      <motion.div variants={sectionVariants} className="flex gap-1 border-b border-brand-border overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-xs font-body -mb-px border-b-2 whitespace-nowrap transition-colors ${
              tab === t.key
                ? 'border-[#00C853] text-brand-text'
                : 'border-transparent text-brand-muted hover:text-brand-secondary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </motion.div>

      {/* Tab content */}
      <motion.div variants={sectionVariants}>
        {tab === 'documents' && <DocumentsTab toolId={deployed?.id ?? null} />}
        {tab === 'overview' && <OverviewPanel tool={tool} deployed={deployed} />}
        {tab === 'executions' && (deployed ? <ToolExecutionsTab toolId={deployed.id} /> : <DeployPrompt label="executions" />)}
        {tab === 'approvals' && (deployed ? <ToolApprovalsTab toolId={deployed.id} /> : <DeployPrompt label="approvals" />)}
        {tab === 'audit' && (deployed ? <ToolAuditTab toolId={deployed.id} /> : <DeployPrompt label="the audit trail" />)}
      </motion.div>

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
