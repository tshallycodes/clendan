import Link from 'next/link'

// ─── Step mock UIs ────────────────────────────────────────────────────────────

function OAuthMockup() {
  return (
    <div className="bg-brand-bg border border-brand-border rounded-sm p-4 space-y-2 font-mono text-xs">
      <p className="text-brand-muted uppercase tracking-widest text-[10px]">Connect a tool</p>
      {['QuickBooks', 'Xero'].map((tool) => (
        <button
          key={tool}
          className="w-full flex items-center justify-between border border-brand-border rounded-sm px-3 py-2 text-brand-text hover:bg-brand-surface transition-colors cursor-default"
        >
          <span>{tool}</span>
          <span className="text-brand-muted">Connect →</span>
        </button>
      ))}
      <div className="flex items-center gap-2 pt-1">
        <span className="w-1.5 h-1.5 rounded-full bg-brand-green inline-block" />
        <span className="text-brand-green">Plaid connected</span>
      </div>
    </div>
  )
}

function WorkerConfigMockup() {
  return (
    <div className="bg-brand-bg border border-brand-border rounded-sm p-4 font-mono text-xs space-y-3">
      <p className="text-brand-muted uppercase tracking-widest text-[10px]">Worker config</p>
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-brand-muted">Worker</span>
          <span className="text-brand-text">Invoice Processing</span>
        </div>
        <div className="flex justify-between">
          <span className="text-brand-muted">Autonomy</span>
          <span className="text-brand-green">Auto + Approval</span>
        </div>
        <div className="flex justify-between">
          <span className="text-brand-muted">Tools</span>
          <span className="text-brand-text">OCR, Accounting, Payments</span>
        </div>
      </div>
      <div className="border-t border-brand-border pt-2 flex justify-end">
        <span className="text-brand-green text-[10px] uppercase tracking-widest">Deploy →</span>
      </div>
    </div>
  )
}

function PolicyMockup() {
  const rows = [
    { label: 'Auto approve', range: '< £500', color: '#00C853' },
    { label: 'Require approval', range: '£500 – £5,000', color: '#00a8cc' },
    { label: 'Block', range: '> £5,000', color: '#ff4d6d' },
  ]
  return (
    <div className="bg-brand-bg border border-brand-border rounded-sm p-4 font-mono text-xs space-y-2">
      <p className="text-brand-muted uppercase tracking-widest text-[10px]">Policy thresholds</p>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between py-1 border-b border-brand-border last:border-0">
          <span style={{ color: r.color }}>{r.label}</span>
          <span className="text-brand-secondary">{r.range}</span>
        </div>
      ))}
    </div>
  )
}

function TerminalMockup() {
  const lines = [
    { text: '▶ Ingesting invoice INV-4821', color: '#a0b8a0' },
    { text: '  OCR extraction complete — 99.2% confidence', color: '#4a6a4a' },
    { text: '  Matched to contract C-0042', color: '#4a6a4a' },
    { text: '  Amount: £380.00 — policy: AUTO', color: '#00C853' },
    { text: '✔ Payment scheduled for 2026-06-10', color: '#00C853' },
  ]
  return (
    <div className="bg-brand-bg border border-brand-border rounded-sm p-4 font-mono text-xs space-y-1">
      <p className="text-brand-muted uppercase tracking-widest text-[10px] mb-2">Execution log</p>
      {lines.map((l, i) => (
        <p key={i} style={{ color: l.color }}>{l.text}</p>
      ))}
    </div>
  )
}

function ApprovalMockup() {
  return (
    <div className="bg-brand-bg border border-brand-border rounded-sm p-4 font-mono text-xs space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-brand-muted uppercase tracking-widest text-[10px]">Approval required</p>
        <span className="text-[10px] px-2 py-0.5 rounded-sm" style={{ background: 'rgba(0,168,204,0.08)', color: '#00a8cc', border: '1px solid rgba(0,168,204,0.2)' }}>Pending</span>
      </div>
      <div className="space-y-1">
        <div className="flex justify-between"><span className="text-brand-muted">Vendor</span><span className="text-brand-text">Acme Corp</span></div>
        <div className="flex justify-between"><span className="text-brand-muted">Amount</span><span className="text-brand-text">£2,400.00</span></div>
        <div className="flex justify-between"><span className="text-brand-muted">Confidence</span><span className="text-brand-green">0.97</span></div>
      </div>
      <div className="flex gap-2 pt-1">
        <button className="flex-1 py-1.5 rounded-sm text-black text-[11px] cursor-default" style={{ background: '#00C853' }}>Approve</button>
        <button className="flex-1 py-1.5 rounded-sm text-[11px] cursor-default" style={{ background: 'rgba(255,77,109,0.1)', border: '1px solid #ff4d6d', color: '#ff4d6d' }}>Block</button>
      </div>
    </div>
  )
}

function AuditMockup() {
  return (
    <div className="bg-brand-bg border border-brand-border rounded-sm p-4 font-mono text-xs space-y-2">
      <p className="text-brand-muted uppercase tracking-widest text-[10px]">Audit entry</p>
      <div className="space-y-1">
        <div className="flex justify-between"><span className="text-brand-muted">Action</span><span className="text-brand-text">payment.scheduled</span></div>
        <div className="flex justify-between"><span className="text-brand-muted">Worker</span><span className="text-brand-text">invoice_processing@1.4.2</span></div>
        <div className="flex justify-between"><span className="text-brand-muted">Trace ID</span><span className="text-brand-muted">cln_tr_8f4d2a</span></div>
        <div className="flex justify-between"><span className="text-brand-muted">Timestamp</span><span className="text-brand-secondary">2026-06-05 09:14:32Z</span></div>
      </div>
      <div className="border-t border-brand-border pt-2 text-brand-muted text-[10px]">
        Reasoning: amount below £500 threshold → auto-approved per policy v3
      </div>
    </div>
  )
}

// ─── Step data ─────────────────────────────────────────────────────────────────

const STEPS = [
  {
    n: '01',
    title: 'Connect Your Tools',
    desc: 'Connect your existing financial systems in one click. No engineering required.',
    mockup: <OAuthMockup />,
  },
  {
    n: '02',
    title: 'Deploy a Worker',
    desc: 'Select a worker, set its role, define its autonomy level, and connect its tools.',
    mockup: <WorkerConfigMockup />,
  },
  {
    n: '03',
    title: 'Set Your Policies',
    desc: 'Define exactly when workers act autonomously and when they ask for your approval.',
    mockup: <PolicyMockup />,
  },
  {
    n: '04',
    title: 'Workers Execute',
    desc: 'Workers run continuously. Every invoice, every transaction, every decision — handled.',
    mockup: <TerminalMockup />,
  },
  {
    n: '05',
    title: 'Review & Approve',
    desc: 'For anything above your threshold, workers pause and route to your queue. One click to approve.',
    mockup: <ApprovalMockup />,
  },
  {
    n: '06',
    title: 'Full Audit Trail',
    desc: 'Every action logged. Every decision explained. Ready for auditors whenever you need it.',
    mockup: <AuditMockup />,
  },
]

const RESULTS = [
  { metric: 'Invoice cost', before: '$6', after: 'under $1' },
  { metric: 'Month-end close', before: '6 days', after: '1–2 days' },
  { metric: 'Hours recovered', before: '', after: '10+ hrs/week' },
]

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function HowItWorksPage() {
  return (
    <div className="bg-brand-bg text-brand-text">

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-16">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">How it works</p>
        <h1
          className="text-4xl md:text-5xl font-heading font-extrabold leading-tight mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          From Invoice to Payment.<br />
          <span className="text-brand-green">Zero Manual Work.</span>
        </h1>
        <p className="font-mono text-sm text-brand-secondary max-w-xl">
          Here&apos;s exactly how Clendan handles your financial operations end to end.
        </p>
      </section>

      {/* Steps */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pb-20 space-y-0">
        {STEPS.map((step, i) => {
          const flip = i % 2 === 1
          return (
            <div
              key={step.n}
              className="grid md:grid-cols-2 gap-12 items-center border-t border-brand-border py-16"
            >
              <div className={flip ? 'md:order-2' : ''}>
                <span
                  className="font-heading font-extrabold text-5xl leading-none"
                  style={{ color: '#1a2a1a', fontFamily: 'var(--font-heading)' }}
                >
                  {step.n}
                </span>
                <h2
                  className="mt-2 mb-3 text-2xl font-heading font-bold"
                  style={{ fontFamily: 'var(--font-heading)' }}
                >
                  {step.title}
                </h2>
                <p className="font-mono text-sm text-brand-secondary leading-relaxed">
                  {step.desc}
                </p>
              </div>
              <div className={flip ? 'md:order-1' : ''}>
                {step.mockup}
              </div>
            </div>
          )
        })}
      </section>

      {/* Results */}
      <section className="border-t border-brand-border bg-brand-surface">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-16">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-6">Results</p>
          <div className="grid md:grid-cols-3 gap-4">
            {RESULTS.map((r) => (
              <div key={r.metric} className="bg-brand-bg border border-brand-border rounded-sm p-6">
                <p className="font-mono text-xs text-brand-muted mb-3">{r.metric}</p>
                <div className="flex items-baseline gap-2">
                  {r.before && (
                    <>
                      <span className="font-heading font-bold text-xl line-through text-brand-muted" style={{ fontFamily: 'var(--font-heading)' }}>{r.before}</span>
                      <span className="text-brand-muted font-mono text-sm">→</span>
                    </>
                  )}
                  <span className="font-heading font-extrabold text-3xl text-brand-green" style={{ fontFamily: 'var(--font-heading)' }}>{r.after}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 py-20 text-center">
        <h2
          className="font-heading font-bold text-3xl mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          Start Automating in 10 Minutes
        </h2>
        <p className="font-mono text-sm text-brand-secondary mb-8">
          Connect your tools, deploy a worker, set your policies. Done.
        </p>
        <Link
          href="/sign-up"
          className="inline-block rounded-sm px-6 py-3 text-sm font-mono font-medium transition-colors hover:bg-[#00a844]"
          style={{ background: '#00C853', color: '#000' }}
        >
          Start Automating in 10 Minutes →
        </Link>
      </section>

    </div>
  )
}
