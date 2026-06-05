import Link from 'next/link'
import { INTEGRATIONS, type Integration } from './integrations-data'

// ─── Sub-components ───────────────────────────────────────────────────────────

function IntegrationCard({ integration }: { integration: Integration }) {
  const isAvailable = integration.status === 'available'
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-heading font-semibold text-brand-text text-[16px] leading-tight">
            {integration.name}
          </p>
          <p className="font-mono text-[12px] text-brand-secondary mt-1">{integration.desc}</p>
        </div>
        <span
          className={`font-mono text-[10px] font-medium uppercase tracking-wider whitespace-nowrap mt-0.5 ${
            isAvailable ? 'text-brand-green' : 'text-brand-muted'
          }`}
        >
          {isAvailable ? 'Available' : 'Coming Soon'}
        </span>
      </div>
      {isAvailable ? (
        <Link
          href="/sign-up"
          className="inline-block text-center bg-brand-green text-black font-mono text-[12px] font-medium px-3 py-1.5 rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all"
        >
          Connect
        </Link>
      ) : (
        <span className="inline-block text-center border border-brand-border text-brand-muted font-mono text-[12px] px-3 py-1.5 rounded-sm cursor-not-allowed">
          Connect
        </span>
      )}
    </div>
  )
}

function CategorySection({ category, items }: { category: string; items: Integration[] }) {
  return (
    <section>
      <h3 className="font-heading font-bold text-[22px] text-brand-text mb-4">{category}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {items.map((item) => (
          <IntegrationCard key={item.name} integration={item} />
        ))}
      </div>
    </section>
  )
}

function HowItWorksStep({ step, title, desc }: { step: string; title: string; desc: string }) {
  return (
    <div className="flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-sm bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)] flex items-center justify-center">
        <span className="font-mono text-brand-green text-[12px] font-medium">{step}</span>
      </div>
      <div>
        <p className="font-heading font-semibold text-brand-text text-[16px]">{title}</p>
        <p className="font-mono text-[12px] text-brand-secondary mt-1">{desc}</p>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  return (
    <div className="bg-brand-bg min-h-screen">
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-14 border-b border-brand-border">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">
          Integrations
        </p>
        <h1 className="font-heading font-extrabold text-[48px] leading-[1.1] text-brand-text max-w-3xl">
          Clendan Works Where You <span className="text-brand-green">Already Work</span>
        </h1>
        <p className="font-mono text-[14px] text-brand-secondary mt-4 max-w-xl">
          Connect your existing financial stack in one click.
        </p>
      </section>

      {/* Integration grid */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 py-14 space-y-12">
        {Object.entries(INTEGRATIONS).map(([category, items]) => (
          <CategorySection key={category} category={category} items={items} />
        ))}
      </section>

      {/* How integrations work */}
      <section className="border-t border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-3">
            How it works
          </p>
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-8">
            Three steps to live data
          </h2>
          <div className="flex flex-col md:flex-row gap-8 md:gap-12">
            <HowItWorksStep
              step="01"
              title="Connect"
              desc="Authenticate via OAuth. Clendan requests only the permissions it needs — read access by default."
            />
            <div className="hidden md:block w-px bg-brand-border self-stretch" />
            <HowItWorksStep
              step="02"
              title="Sync"
              desc="An initial data pull runs immediately. Historical transactions, invoices, and balances are indexed and validated."
            />
            <div className="hidden md:block w-px bg-brand-border self-stretch" />
            <HowItWorksStep
              step="03"
              title="Live"
              desc="Continuous updates via webhooks and polling. Your workers always operate on current data."
            />
          </div>
        </div>
      </section>

      {/* Security note */}
      <section className="border-t border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-10">
          <div className="bg-brand-surface border border-brand-border rounded-sm p-6 flex flex-col sm:flex-row gap-4 items-start">
            <div className="flex-shrink-0 font-mono text-[10px] uppercase tracking-widest text-brand-muted pt-0.5">
              Security
            </div>
            <p className="font-mono text-[13px] text-brand-secondary">
              Credentials encrypted at rest. Never stored in plaintext. Full permission scoping —
              Clendan only requests access it actively uses. OAuth tokens are stored with
              tenant-level encryption keys and are never logged or exposed in API responses.
            </p>
          </div>
        </div>
      </section>

      {/* Custom integration CTA */}
      <section className="border-t border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14 text-center">
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-3">
            Need a custom integration?
          </h2>
          <p className="font-mono text-[14px] text-brand-secondary mb-6">
            We can connect Clendan to any system with an API.
          </p>
          <a
            href="mailto:hello@clendan.com"
            className="inline-block bg-brand-green text-black font-mono text-[13px] font-medium px-6 py-3 rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all"
          >
            Get in touch
          </a>
        </div>
      </section>
    </div>
  )
}
