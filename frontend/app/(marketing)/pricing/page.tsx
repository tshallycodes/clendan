import Link from 'next/link'
import { PricingToggle } from './PricingToggle'
import { PricingFAQ } from './PricingFAQ'
import { PLANS, COMPARISON, type Plan, type CellValue } from './pricing-data'

// ─── Sub-components ───────────────────────────────────────────────────────────

function CheckMark() {
  return <span className="text-brand-green font-mono text-[14px]">✓</span>
}

function Dash() {
  return <span className="text-brand-muted font-mono text-[14px]">—</span>
}

function ComparisonCell({ value }: { value: CellValue }) {
  if (value === true) return <CheckMark />
  if (value === false) return <Dash />
  return <span className="font-mono text-[12px] text-brand-secondary">{value}</span>
}

function PlanCard({ plan }: { plan: Plan }) {
  const borderClass = plan.highlight
    ? 'border-2 border-brand-green'
    : 'border border-brand-border'

  return (
    <div className={`bg-brand-surface rounded-sm p-6 flex flex-col gap-5 relative ${borderClass}`}>
      {plan.badge && (
        <span className="absolute -top-3 left-6 bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)] text-brand-green font-mono text-[10px] uppercase tracking-widest px-3 py-1 rounded-sm">
          {plan.badge}
        </span>
      )}
      <div>
        <h3 className="font-heading font-bold text-[22px] text-brand-text">{plan.name}</h3>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="font-heading font-extrabold text-[32px] text-brand-text">
            {plan.monthlyPrice}
          </span>
          {plan.monthlyPrice !== 'Custom' && (
            <span className="font-mono text-[12px] text-brand-muted">/month</span>
          )}
        </div>
        {plan.annualPrice !== 'Custom' && (
          <p className="font-mono text-[11px] text-brand-muted mt-1">
            {plan.annualPrice}/month billed annually
          </p>
        )}
      </div>
      <ul className="space-y-2 flex-1">
        {plan.features.map((f) => (
          <li key={f.label} className="flex items-start gap-2">
            <span className={`mt-0.5 flex-shrink-0 ${f.included ? 'text-brand-green' : 'text-brand-muted'}`}>
              {f.included ? '✓' : '—'}
            </span>
            <span className={`font-mono text-[12px] ${f.included ? 'text-brand-secondary' : 'text-brand-muted'}`}>
              {f.label}
            </span>
          </li>
        ))}
      </ul>
      {plan.ctaExternal ? (
        <a
          href={plan.ctaHref}
          className={`text-center font-mono text-[13px] font-medium px-4 py-3 rounded-sm transition-all active:scale-[0.97] ${
            plan.highlight
              ? 'bg-brand-green text-black hover:bg-[#00a844]'
              : 'border border-brand-border text-brand-text hover:bg-brand-elevated'
          }`}
        >
          {plan.cta}
        </a>
      ) : (
        <Link
          href={plan.ctaHref}
          className={`text-center font-mono text-[13px] font-medium px-4 py-3 rounded-sm transition-all active:scale-[0.97] ${
            plan.highlight
              ? 'bg-brand-green text-black hover:bg-[#00a844]'
              : 'border border-brand-border text-brand-text hover:bg-brand-elevated'
          }`}
        >
          {plan.cta}
        </Link>
      )}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function PricingPage() {
  return (
    <div className="bg-brand-bg min-h-screen">
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-14 border-b border-brand-border">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">
          Pricing
        </p>
        <h1 className="font-heading font-extrabold text-[48px] leading-[1.1] text-brand-text">
          Simple, Transparent Pricing
        </h1>
        <p className="font-mono text-[14px] text-brand-secondary mt-4">
          No hidden fees. No usage surprises. Cancel any time.
        </p>
        <div className="mt-8">
          <PricingToggle />
        </div>
      </section>

      {/* Plan cards */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 py-14">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          {PLANS.map((plan) => (
            <PlanCard key={plan.id} plan={plan} />
          ))}
        </div>
      </section>

      {/* Feature comparison table */}
      <section className="border-t border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-3">
            Compare plans
          </p>
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-8">
            Full feature breakdown
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-brand-border">
                  <th className="text-left font-mono text-[11px] uppercase tracking-widest text-brand-muted pb-3 pr-4 w-1/3">
                    Feature
                  </th>
                  {(['Starter', 'Growth', 'Enterprise'] as const).map((col) => (
                    <th key={col} className="text-center font-heading font-semibold text-[14px] text-brand-text pb-3 px-4">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARISON.map((row, i) => (
                  <tr key={row.feature} className={`border-b border-brand-border ${i % 2 === 0 ? '' : 'bg-brand-surface'}`}>
                    <td className="font-mono text-[12px] text-brand-secondary py-3 pr-4">{row.feature}</td>
                    <td className="text-center py-3 px-4"><ComparisonCell value={row.starter} /></td>
                    <td className="text-center py-3 px-4"><ComparisonCell value={row.growth} /></td>
                    <td className="text-center py-3 px-4"><ComparisonCell value={row.enterprise} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-3">FAQ</p>
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-8">Common questions</h2>
          <PricingFAQ />
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="border-t border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-16 text-center">
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-3">
            Start with a 14-day free trial
          </h2>
          <p className="font-mono text-[14px] text-brand-secondary mb-8">No credit card required.</p>
          <Link
            href="/sign-up"
            className="inline-block bg-brand-green text-black font-mono text-[13px] font-medium px-8 py-3.5 rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all"
          >
            Get started free
          </Link>
        </div>
      </section>
    </div>
  )
}
