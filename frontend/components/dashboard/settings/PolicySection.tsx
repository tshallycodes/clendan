'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { ConfigDrawer } from '@/components/dashboard/tools/ConfigDrawer'
import { formatType } from '@/components/dashboard/tools/ToolCard'
import type { Tool } from '@/components/dashboard/tools/ToolCard'
import { useCanConfigure } from '@/lib/auth-client'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const AUTONOMY_BADGE: Record<Tool['autonomy_level'], string> = {
  auto:    'bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]',
  approve: 'bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]',
  suggest: 'bg-brand-surface text-brand-muted border border-brand-border',
}

export function PolicySection() {
  const { getToken } = useAuth()
  const canConfigure = useCanConfigure()
  const [tools, setTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTool, setActiveTool] = useState<Tool | null>(null)

  async function fetchTools() {
    const token = await getToken()
    const res = await fetch(`${API}/v1/tools`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      const json = await res.json()
      setTools((json.data?.tools ?? json.data ?? []) as Tool[])
    }
    setLoading(false)
  }

  useEffect(() => { fetchTools() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2].map((i) => (
          <div key={i} className="h-14 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />
        ))}
      </div>
    )
  }

  if (tools.length === 0) {
    return (
      <div className="border border-brand-border rounded-sm px-4 py-6 text-center space-y-2">
        <p className="text-xs font-mono text-brand-muted">
          No tools deployed yet. Deploy a tool from the Tools page to configure its policy.
        </p>
        <Link
          href="/tools"
          className="text-[10px] font-mono text-brand-secondary hover:text-brand-text transition-colors"
        >
          Go to Tools →
        </Link>
      </div>
    )
  }

  return (
    <>
      <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
        {tools.map((tool) => {
          const isActive = tool.status === 'active'
          return (
            <div key={tool.id} className="bg-brand-surface px-4 py-3 flex items-center gap-4">
              <div className="flex-1 flex items-center gap-2 min-w-0">
                <span className="text-xs font-mono text-brand-text font-medium truncate">
                  {formatType(tool.type)}
                </span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm ${AUTONOMY_BADGE[tool.autonomy_level]}`}>
                  {tool.autonomy_level}
                </span>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <div className="flex items-center gap-1.5">
                  {isActive ? (
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00C853] opacity-60" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00C853]" />
                    </span>
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-brand-muted" />
                  )}
                  <span className={`text-[10px] font-mono ${isActive ? 'text-[#00C853]' : 'text-brand-muted'}`}>
                    {isActive ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {canConfigure && (
                  <button
                    type="button"
                    onClick={() => setActiveTool(tool)}
                    className="text-xs font-mono border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-2.5 py-1 transition-colors"
                  >
                    Configure
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {activeTool && (
        <ConfigDrawer
          tool={activeTool}
          toolType={activeTool.type}
          onClose={() => setActiveTool(null)}
          onSaved={() => { fetchTools(); setActiveTool(null) }}
        />
      )}
    </>
  )
}
