import Link from 'next/link'
import { Zap, Link2, ShieldCheck } from 'lucide-react'

// ─── Social Proof Strip ────────────────────────────────────────────────────

const INTEGRATIONS = ['Xero', 'QuickBooks', 'Plaid', 'Stripe', 'NetSuite', 'Salesforce']

export function SocialProofStrip() {
  return (
    <div className="border-y border-brand-border" style={{ background: '#111118' }}>
      <div className="max-w-6xl mx-auto px-6 md:px-8 py-5 flex items-center gap-6 overflow-x-auto no-scrollbar">
        <span className="text-xs font-mono text-brand-muted shrink-0">Trusted integrations with:</span>
        <div className="flex items-center gap-6 shrink-0">
          {INTEGRATIONS.map((name) => (
            <span key={name} className="text-sm font-mono text-brand-muted hover:text-brand-secondary transition-colors shrink-0">
              {name}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Problem Statement ─────────────────────────────────────────────────────

const STATS = [
  { figure: '66%', claim: 'of AP teams still process invoices manually', source: 'Ardent Partners 2025' },
  { figure: '50%', claim: 'of finance teams take 6+ days to close the books each month', source: 'Ledge 2025' },
  { figure: '$6+', claim: 'average cost to manually process a single invoice', source: 'industry average' },
]

export function ProblemStatement() {
  return (
    <section className="max-w-6xl mx-auto px-6 md:px-8 py-20">
      <h2 className="font-heading text-2xl font-bold text-brand-text mb-8">Finance Operations Are Broken</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {STATS.map((s) => (
          <div key={s.figure} className="bg-brand-surface border border-brand-border rounded-sm p-6 flex flex-col gap-3">
            <span className="font-heading text-4xl font-bold" style={{ color: '#00C853' }}>{s.figure}</span>
            <p className="text-sm font-mono text-brand-secondary leading-relaxed">{s.claim}</p>
            <span className="text-xs font-mono text-brand-muted mt-auto">{s.source}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

// ─── Solution Overview ─────────────────────────────────────────────────────

const SOLUTIONS = [
  { icon: Zap, title: 'Deploy AI Workers', desc: 'Autonomous agents that execute real financial tasks, not just surface insights.' },
  { icon: Link2, title: 'Connect Your Tools', desc: 'Native integrations with Xero, QuickBooks, Plaid, Stripe, and your ERP.' },
  { icon: ShieldCheck, title: 'Full Audit Trail', desc: 'Every action logged, every decision explained. Policy-enforced by default.' },
]

export function SolutionOverview() {
  return (
    <section className="border-y border-brand-border" style={{ background: '#111118' }}>
      <div className="max-w-6xl mx-auto px-6 md:px-8 py-20">
        <h2 className="font-heading text-xl font-bold text-brand-text mb-2 max-w-2xl">
          Deploy AI Workers. Connect Your Tools. Execute With a Full Audit Trail.
        </h2>
        <p className="text-sm font-mono text-brand-muted mb-10">Infrastructure, not a dashboard.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SOLUTIONS.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="bg-brand-bg border border-brand-border rounded-sm p-6 flex flex-col gap-4">
              <Icon size={18} className="text-brand-secondary" />
              <div>
                <h3 className="font-heading text-sm font-semibold text-brand-text mb-1">{title}</h3>
                <p className="text-xs font-mono text-brand-muted leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── CTA Banner ────────────────────────────────────────────────────────────

export function CTABanner() {
  return (
    <section className="max-w-6xl mx-auto px-6 md:px-8 py-20">
      <div
        className="rounded-sm p-10 md:p-14 text-center flex flex-col items-center gap-6"
        style={{ background: '#111118', border: '1px solid rgba(0,200,83,0.2)' }}
      >
        <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text">
          Ready to Automate Your Finance Stack?
        </h2>
        <p className="text-sm font-mono text-brand-secondary max-w-sm">
          Deploy your first AI worker in under 10 minutes.
        </p>
        <Link
          href="/sign-up"
          className="rounded-sm px-6 py-3 text-sm font-mono font-medium transition-colors"
          style={{ background: '#00C853', color: '#000' }}
        >
          Request Early Access
        </Link>
      </div>
    </section>
  )
}
