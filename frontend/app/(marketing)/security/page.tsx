import Link from 'next/link'

export const metadata = {
  title: 'Security — Clendan',
  description: 'Every decision auditable. Every credential encrypted. Every tenant isolated.',
}

const PRINCIPLES = [
  {
    title: 'Data Encryption',
    body: 'All data encrypted at rest using AES-256. All data in transit protected by TLS 1.3. Tenant API credentials encrypted with tenant-specific keys and never logged.',
  },
  {
    title: 'Tenant Isolation',
    body: 'PostgreSQL row-level security enforced on every table. No query executes without tenant scope. Agent instances are fully isolated — one tenant\'s workers cannot access another\'s data or tools.',
  },
  {
    title: 'Audit Immutability',
    body: 'Every agent action written to an append-only audit log before the response is returned. Audit rows are never edited or deleted. Full reasoning traces stored without truncation.',
  },
  {
    title: 'Access Controls',
    body: 'Role-based access control enforced at both the application and database layer. All protected routes require server-side JWT verification via Clerk. Least-privilege principle applied to all service accounts.',
  },
]

const DATA_HANDLING = [
  'Email address and company name collected at signup',
  'Financial document data processed on your behalf and not retained beyond 30 days',
  'AI reasoning traces stored for audit purposes per your plan tier',
  'No financial data written to application logs — trace IDs used for correlation only',
  'Data residency: UK and EU only',
  'Account data retained until you delete your account',
  'Audit logs retained per plan tier — see your plan details',
  'Processed documents purged after 30 days',
]

export default function SecurityPage() {
  return (
    <div className="bg-brand-bg text-brand-text">
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-14">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">
          Security
        </p>
        <h1
          className="text-4xl md:text-5xl font-heading font-extrabold leading-tight mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          Security Built for<br />
          <span className="text-brand-green">Financial Infrastructure</span>
        </h1>
        <p className="font-mono text-sm text-brand-secondary max-w-xl">
          Every decision auditable. Every credential encrypted. Every tenant isolated.
        </p>
      </section>

      {/* Principles grid */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pb-20">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-6">
          Security Principles
        </p>
        <div className="grid md:grid-cols-2 gap-4">
          {PRINCIPLES.map((p) => (
            <div
              key={p.title}
              className="bg-brand-surface border border-brand-border rounded-sm p-6"
              style={{ borderLeft: '3px solid #00C853' }}
            >
              <h2
                className="font-heading font-bold text-base mb-3"
                style={{ fontFamily: 'var(--font-heading)' }}
              >
                {p.title}
              </h2>
              <p className="font-mono text-xs text-brand-secondary leading-relaxed">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* SOC 2 */}
      <section className="bg-brand-surface border-t border-b border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-14">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-6">
            Compliance
          </p>
          <div className="flex flex-col md:flex-row gap-8 items-start">
            <div className="flex-1">
              <h2
                className="font-heading font-bold text-2xl mb-3"
                style={{ fontFamily: 'var(--font-heading)' }}
              >
                SOC 2 Type II In Progress
              </h2>
              <p className="font-mono text-sm text-brand-secondary leading-relaxed">
                Clendan is working toward SOC 2 Type II certification, targeting Q4 2026. Our
                security controls — encryption, access control, audit logging, and incident
                response — are designed to meet SOC 2 Trust Service Criteria from day one.
              </p>
            </div>
            <div className="bg-brand-bg border border-brand-border rounded-sm p-5 shrink-0 min-w-56">
              <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-3">
                Current Status
              </p>
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-brand-secondary">Audit in progress</span>
                  <span
                    className="text-[10px] font-mono px-2 py-0.5 rounded-sm"
                    style={{
                      background: 'rgba(0,168,204,0.08)',
                      color: '#00a8cc',
                      border: '1px solid rgba(0,168,204,0.2)',
                    }}
                  >
                    Active
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-brand-secondary">Target date</span>
                  <span className="font-mono text-xs text-brand-text">Q4 2026</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Data handling */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 py-16">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-6">
          Data Handling
        </p>
        <div className="grid md:grid-cols-2 gap-10">
          <div>
            <h2
              className="font-heading font-bold text-xl mb-5"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              What We Store and Why
            </h2>
            <ul className="flex flex-col gap-3">
              {DATA_HANDLING.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="text-brand-green font-mono text-xs mt-0.5 shrink-0">—</span>
                  <span className="font-mono text-xs text-brand-secondary leading-relaxed">
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Vulnerability disclosure */}
          <div className="bg-brand-surface border border-brand-border rounded-sm p-6">
            <h2
              className="font-heading font-bold text-lg mb-4"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              Vulnerability Disclosure
            </h2>
            <p className="font-mono text-xs text-brand-secondary leading-relaxed mb-4">
              If you discover a security issue, please report it responsibly. We take all reports
              seriously.
            </p>
            <div className="flex flex-col gap-3">
              <div className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
                <p className="font-mono text-[10px] text-brand-muted mb-0.5">Report to</p>
                <a
                  href="mailto:security@clendan.com"
                  className="font-mono text-xs text-brand-text hover:text-brand-green transition-colors"
                >
                  security@clendan.com
                </a>
              </div>
              <div className="flex flex-col gap-1 pl-1">
                <p className="font-mono text-xs text-brand-secondary">
                  — Acknowledged within 48 hours
                </p>
                <p className="font-mono text-xs text-brand-secondary">
                  — Status update within 7 days
                </p>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-brand-border">
              <Link
                href="/security-policy"
                className="font-mono text-xs text-brand-green hover:text-brand-text transition-colors"
              >
                Read our full security policy →
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
