type Phase = 'MVP' | 'V2' | 'V3'

interface Worker {
  name: string
  phase: Phase
  desc: string
}

const WORKERS: Worker[] = [
  { name: 'Invoice Processing', phase: 'MVP', desc: 'Receive, extract, validate, and route invoices automatically.' },
  { name: 'AI Accountant', phase: 'MVP', desc: 'Journal entries, GL coding, and month-end close tasks.' },
  { name: 'Reconciliation', phase: 'V2', desc: 'Match transactions across bank, ERP, and payment processors.' },
  { name: 'Expense Control', phase: 'V2', desc: 'Enforce spend policy and flag out-of-policy submissions.' },
  { name: 'Collections', phase: 'V2', desc: 'Automated AR follow-ups, escalations, and payment matching.' },
  { name: 'Fraud Detection', phase: 'V2', desc: 'Anomaly detection on transactions and supplier behaviour.' },
  { name: 'Treasury', phase: 'V2', desc: 'Cash positioning, sweep rules, and liquidity forecasting.' },
  { name: 'Revenue Recognition', phase: 'V2', desc: 'ASC 606 / IFRS 15 compliant revenue scheduling.' },
  { name: 'Credit Underwriting', phase: 'V3', desc: 'Automated decisioning on trade credit and lending applications.' },
  { name: 'Compliance', phase: 'V3', desc: 'Continuous monitoring against regulatory frameworks.' },
]

const PHASE_STYLES: Record<Phase, { bg: string; text: string; border: string }> = {
  MVP: { bg: 'rgba(0,200,83,0.08)', text: '#00C853', border: 'rgba(0,200,83,0.2)' },
  V2:  { bg: 'rgba(0,168,204,0.08)', text: '#00a8cc', border: 'rgba(0,168,204,0.2)' },
  V3:  { bg: 'transparent', text: '#4a6a4a', border: '#1a2a1a' },
}

function PhaseBadge({ phase }: { phase: Phase }) {
  const s = PHASE_STYLES[phase]
  return (
    <span
      className="text-xs font-mono px-2 py-0.5 rounded-sm"
      style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
    >
      {phase}
    </span>
  )
}

export function WorkerShowcase() {
  return (
    <section className="border-y border-brand-border" style={{ background: '#111118' }}>
      <div className="max-w-6xl mx-auto px-6 md:px-8 py-20">
        <p className="text-xs font-mono text-brand-muted uppercase tracking-widest mb-3">Workers</p>
        <h2 className="font-heading text-2xl font-bold text-brand-text mb-10">
          10 AI Workers. Every Finance Function Covered.
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {WORKERS.map((w) => (
            <div
              key={w.name}
              className="bg-brand-bg border border-brand-border rounded-sm p-4 flex flex-col gap-3"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-heading text-xs font-semibold text-brand-text leading-snug">{w.name}</h3>
                <PhaseBadge phase={w.phase} />
              </div>
              <p className="text-xs font-mono text-brand-muted leading-relaxed">{w.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
