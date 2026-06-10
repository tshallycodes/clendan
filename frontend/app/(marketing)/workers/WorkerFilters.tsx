'use client'

import { useState } from 'react'
import type { Worker } from './page'

type Phase = 'All' | 'MVP' | 'V2' | 'V3'

const PHASE_TABS: Phase[] = ['All', 'MVP', 'V2', 'V3']

const PHASE_BADGE: Record<string, { bg: string; color: string; border: string; label: string }> = {
  MVP: { bg: 'rgba(0,200,83,0.08)', color: '#00C853', border: 'rgba(0,200,83,0.2)', label: 'MVP' },
  V2:  { bg: 'rgba(0,168,204,0.08)', color: '#00a8cc', border: 'rgba(0,168,204,0.2)', label: 'V2' },
  V3:  { bg: 'rgba(74,106,74,0.15)', color: '#4a6a4a', border: 'rgba(74,106,74,0.3)', label: 'V3' },
}

function PhaseBadge({ phase }: { phase: string }) {
  const s = PHASE_BADGE[phase]
  return (
    <span
      className="font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm"
      style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}
    >
      {s.label}
    </span>
  )
}

function WorkerCard({ worker }: { worker: Worker }) {
  const deployable = worker.phase === 'MVP'
  return (
    <div
      className="bg-brand-surface border border-brand-border rounded-sm p-5 flex flex-col gap-4"
      style={deployable ? { borderLeft: '3px solid #00C853' } : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <h3
          className="font-heading font-semibold text-base leading-snug"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          {worker.name}
        </h3>
        <PhaseBadge phase={worker.phase} />
      </div>

      <p className="font-mono text-xs text-brand-secondary leading-relaxed flex-1">
        {worker.desc}
      </p>

      <div className="flex flex-wrap gap-1.5">
        {worker.tools.map((tool) => (
          <span
            key={tool}
            className="font-mono text-[10px] px-2 py-0.5 rounded-sm"
            style={{
              background: '#0a0a0a',
              border: '1px solid #1a2a1a',
              color: '#4a6a4a',
            }}
          >
            {tool}
          </span>
        ))}
      </div>

      <div className="pt-1">
        {deployable ? (
          <a
            href="/sign-up"
            className="inline-block rounded-sm px-4 py-2 text-xs font-mono font-medium transition-colors hover:bg-[#00a844]"
            style={{ background: '#00C853', color: '#000' }}
          >
            Deploy
          </a>
        ) : (
          <div className="relative group inline-block">
            <button
              disabled
              className="rounded-sm px-4 py-2 text-xs font-mono cursor-not-allowed"
              style={{ border: '1px solid #1a2a1a', color: '#4a6a4a' }}
            >
              Deploy
            </button>
            <span
              className="absolute bottom-full left-0 mb-1.5 hidden group-hover:block font-mono text-[10px] whitespace-nowrap rounded-sm px-2 py-1 z-10"
              style={{ background: '#1a1a1a', border: '1px solid #1a2a1a', color: '#a0b8a0' }}
            >
              Coming soon
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export function WorkerFilters({ workers }: { workers: Worker[] }) {
  const [active, setActive] = useState<Phase>('All')

  const filtered = active === 'All' ? workers : workers.filter((w) => w.phase === active)

  return (
    <section className="max-w-6xl mx-auto px-6 md:px-8 pb-12">
      {/* Filter tabs */}
      <div className="flex items-center gap-1 mb-8 border-b border-brand-border pb-4">
        {PHASE_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActive(tab)}
            className="font-mono text-xs px-4 py-2 rounded-sm transition-colors"
            style={{
              background: active === tab ? '#1a1a1a' : 'transparent',
              color: active === tab ? '#e8f0e8' : '#4a6a4a',
              border: active === tab ? '1px solid #1a2a1a' : '1px solid transparent',
            }}
          >
            {tab}
          </button>
        ))}
        <span className="ml-auto font-mono text-xs text-brand-muted">
          {filtered.length} worker{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((w) => (
          <WorkerCard key={w.name} worker={w} />
        ))}
      </div>
    </section>
  )
}
