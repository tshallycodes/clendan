// ─── Sub-components ───────────────────────────────────────────────────────────

interface FounderCardProps {
  role: string
  name: string
  initials: string
}

// TODO: Replace with real team photos and bios
function FounderCard({ role, name, initials }: FounderCardProps) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-sm p-6 flex flex-col gap-4">
      <div className="w-14 h-14 rounded-sm bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)] flex items-center justify-center flex-shrink-0">
        <span className="font-heading font-bold text-[18px] text-brand-green">{initials}</span>
      </div>
      <div>
        <p className="font-heading font-bold text-[16px] text-brand-text">{name}</p>
        <p className="font-mono text-[12px] text-brand-secondary mt-0.5">{role}</p>
      </div>
      <a
        href="https://linkedin.com"
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`${name} on LinkedIn`}
        className="font-mono text-[11px] text-brand-muted hover:text-brand-secondary transition-colors flex items-center gap-1.5"
      >
        <LinkedInIcon />
        LinkedIn
      </a>
    </div>
  )
}

function LinkedInIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  )
}

interface RoadmapPhaseProps {
  phase: string
  title: string
  isLast?: boolean
}

function RoadmapPhase({ phase, title, isLast = false }: RoadmapPhaseProps) {
  return (
    <div className="flex items-start gap-4">
      <div className="flex flex-col items-center">
        <div className="w-8 h-8 rounded-sm bg-[rgba(0,200,83,0.08)] border border-[rgba(0,200,83,0.2)] flex items-center justify-center flex-shrink-0">
          <span className="font-mono text-brand-green text-[10px] font-medium">{phase}</span>
        </div>
        {!isLast && (
          <div className="w-px flex-1 mt-2 bg-brand-border" style={{ minHeight: '32px' }} />
        )}
      </div>
      <div className="pt-1 pb-8">
        <p className="font-heading font-semibold text-[16px] text-brand-text">{title}</p>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AboutPage() {
  return (
    <div className="bg-brand-bg min-h-screen">
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-14 border-b border-brand-border">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">
          About
        </p>
        <h1 className="font-heading font-extrabold text-[48px] leading-[1.1] text-brand-text max-w-3xl">
          Finance Teams Shouldn&apos;t Be Doing{' '}
          <span className="text-brand-green">Repetitive Work</span>
        </h1>
      </section>

      {/* Founding story */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 py-14 border-b border-brand-border">
        <div className="max-w-3xl space-y-6">
          <p className="font-mono text-[14px] text-brand-secondary leading-relaxed">
            Clendan was born from a simple observation: finance teams spend most of their time on
            execution — processing invoices, reconciling accounts, chasing approvals. These are
            deterministic, rule-based tasks that AI can handle reliably. We built Clendan to give
            every finance team the autonomous infrastructure to focus on decisions, not execution.
          </p>

          {/* Mission block */}
          <div className="bg-brand-surface border-l-4 border-l-brand-green rounded-sm p-6">
            <p className="font-heading font-semibold text-[16px] text-brand-text leading-snug">
              Our mission: give every finance team the autonomous infrastructure to focus on
              decisions, not execution.
            </p>
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="border-b border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-3">
            Team
          </p>
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-8">
            The people building it
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl">
            <FounderCard role="Founder / CEO" name="[Name]" initials="CE" />
            <FounderCard role="Founder / CTO" name="[Name]" initials="CT" />
          </div>
        </div>
      </section>

      {/* What we're building — roadmap */}
      <section className="border-b border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-3">
            Roadmap
          </p>
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-10">
            What we&apos;re building
          </h2>
          <div className="max-w-sm">
            <RoadmapPhase phase="P1" title="Invoice processing MVP" />
            <RoadmapPhase phase="P2" title="Full finance automation suite" />
            <RoadmapPhase phase="P3" title="Universal finance OS" isLast />
          </div>
        </div>
      </section>

      {/* Contact */}
      <section>
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-3">
            Contact
          </p>
          <h2 className="font-heading font-bold text-[32px] text-brand-text mb-6">
            Get in touch
          </h2>
          <div className="flex flex-wrap items-center gap-4">
            <a
              href="mailto:hello@clendan.com"
              className="font-mono text-[13px] text-brand-secondary hover:text-brand-text transition-colors"
            >
              hello@clendan.com
            </a>
            <span className="text-brand-border font-mono">|</span>
            <a
              href="https://linkedin.com/company/clendan"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[13px] text-brand-secondary hover:text-brand-text transition-colors flex items-center gap-1.5"
            >
              <LinkedInIcon />
              LinkedIn
            </a>
            <span className="text-brand-border font-mono">|</span>
            <a
              href="https://x.com/clendan"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[13px] text-brand-secondary hover:text-brand-text transition-colors flex items-center gap-1.5"
            >
              <XIcon />
              X / Twitter
            </a>
          </div>
        </div>
      </section>
    </div>
  )
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.748l7.73-8.835L1.254 2.25H8.08l4.266 5.64L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z" />
    </svg>
  )
}
