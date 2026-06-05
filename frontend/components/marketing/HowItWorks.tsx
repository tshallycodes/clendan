const STEPS = [
  { num: '01', title: 'Connect', desc: 'Link your bank, ERP, and accounting tools via OAuth in minutes.' },
  { num: '02', title: 'Configure', desc: 'Set policy rules, approval thresholds, and worker permissions.' },
  { num: '03', title: 'Execute', desc: 'Workers run autonomously, enforcing policy on every action.' },
  { num: '04', title: 'Monitor', desc: 'Full audit trail. Every decision, every outcome, every trace ID.' },
]

export function HowItWorks() {
  return (
    <section className="max-w-6xl mx-auto px-6 md:px-8 py-20">
      <p className="text-xs font-mono text-brand-muted uppercase tracking-widest mb-3">How it works</p>
      <h2 className="font-heading text-2xl font-bold text-brand-text mb-12">
        From Invoice to Payment in Under 30 Seconds
      </h2>

      <div className="relative">
        {/* Desktop connector line */}
        <div
          className="hidden md:block absolute top-6 left-0 right-0 h-px"
          style={{
            background: 'repeating-linear-gradient(to right, #1a2a1a 0px, #1a2a1a 6px, transparent 6px, transparent 14px)',
            zIndex: 0,
          }}
          aria-hidden
        />

        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 relative z-10">
          {STEPS.map((step) => (
            <div key={step.num} className="flex flex-col gap-4">
              <div
                className="w-12 h-12 flex items-center justify-center rounded-sm shrink-0"
                style={{ background: '#0a0a0f', border: '1px solid #1a2a1a' }}
              >
                <span className="font-heading text-sm font-bold" style={{ color: '#00C853' }}>
                  {step.num}
                </span>
              </div>
              <div>
                <h3 className="font-heading text-sm font-semibold text-brand-text mb-1.5">{step.title}</h3>
                <p className="text-xs font-mono text-brand-muted leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
