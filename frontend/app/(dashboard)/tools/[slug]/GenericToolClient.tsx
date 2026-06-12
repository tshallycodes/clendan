'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import { DeployToolForm } from '@/components/dashboard/tools/DeployToolForm'
import { ExecutionsTable } from '@/components/dashboard/tools/ExecutionsTable'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import type { Execution } from '@/components/dashboard/tools/ToolDetail'
import type { ToolDef } from '../tools-data'
import { useAuth } from '@clerk/nextjs'
import { useCanConfigure } from '@/lib/auth-client'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Props {
  tool: ToolDef
  deployed: Tool | null
  executions: Execution[]
}

const AUTONOMY_BADGE: Record<string, { label: string; className: string }> = {
  auto:    { label: 'Auto',    className: 'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]' },
  approve: { label: 'Approve', className: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]' },
  suggest: { label: 'Suggest', className: 'bg-[#111111] text-[#4a6a4a] border border-[#1a2a1a]' },
}

export function GenericToolClient({ tool, deployed, executions }: Props) {
  const router = useRouter()
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const [showConfig, setShowConfig] = useState(false)
  const [toggling, setToggling] = useState(false)

  const isActive = deployed?.status === 'active'
  const badge = deployed ? (AUTONOMY_BADGE[deployed.autonomy_level] ?? AUTONOMY_BADGE.suggest) : null

  async function handleToggle() {
    if (!deployed) return
    setToggling(true)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/tools/${deployed.id}/pause`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      router.refresh()
    } finally {
      setToggling(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <Link href="/tools" className="text-[11px] font-mono text-[#4a6a4a] hover:text-[#a0b8a0] transition-colors">
        ← Tools
      </Link>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-heading font-bold text-2xl text-[#e8f0e8]">{tool.name}</h1>
            {deployed && badge && (
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${badge.className}`}>{badge.label}</span>
            )}
            {deployed && (
              <span className="text-[10px] font-mono text-[#4a6a4a]">v{deployed.version}</span>
            )}
          </div>
          <p className="text-xs font-mono text-[#4a6a4a] max-w-xl">{tool.desc}</p>
        </div>

        {deployed && canConfigure && (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => setShowConfig(true)}
              className="text-xs font-mono border border-[#1a2a1a] text-[#e8f0e8] hover:bg-[#1a1a28] rounded-sm px-3 py-1.5 transition-colors"
            >
              Configure
            </button>
            <button
              type="button"
              onClick={handleToggle}
              disabled={toggling}
              className="text-xs font-mono border border-[#1a2a1a] text-[#e8f0e8] hover:bg-[#1a1a28] rounded-sm px-3 py-1.5 transition-colors disabled:opacity-50"
            >
              {toggling ? '…' : isActive ? 'Pause' : 'Resume'}
            </button>
          </div>
        )}
      </div>

      {deployed ? (
        <div className="flex items-center gap-2">
          {isActive ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-60" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00C853]" />
            </span>
          ) : (
            <span className="h-2 w-2 rounded-full bg-[#4a6a4a]" />
          )}
          <span className={`text-xs font-mono ${isActive ? 'text-[#00C853]' : 'text-[#4a6a4a]'}`}>
            {isActive ? 'Active' : 'Inactive'}
          </span>
        </div>
      ) : (
        <div className="bg-[#111111] border border-[#1a2a1a] rounded-sm p-6 space-y-4 max-w-sm">
          <p className="text-xs font-mono text-[#4a6a4a]">This tool has not been deployed yet.</p>
          {canConfigure && (
            <DeployToolForm fixedType={tool.type} onDeployed={() => router.refresh()} />
          )}
        </div>
      )}

      {tool.capabilities.length > 0 && (
        <section className="space-y-3">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a]">Capabilities</p>
          <ul className="bg-[#111111] border border-[#1a2a1a] rounded-sm divide-y divide-[#1a2a1a]">
            {tool.capabilities.map((cap) => (
              <li key={cap} className="flex items-start gap-3 px-4 py-3">
                <span className="text-[#00C853] font-mono text-[10px] mt-0.5 shrink-0">→</span>
                <span className="text-xs font-mono text-[#a0b8a0]">{cap}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {deployed && (
        <section className="space-y-3">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#4a6a4a]">Recent Executions</p>
          <ExecutionsTable executions={executions} />
        </section>
      )}

      {showConfig && deployed && (
        <ConfigDrawer
          tool={deployed}
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); router.refresh() }}
        />
      )}
    </div>
  )
}
