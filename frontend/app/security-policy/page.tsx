import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'

export const metadata = {
  title: 'Security Policy — Clendan',
}

const SCOPE_DOMAINS = [
  'api.clendan.com — backend API and agent execution endpoints',
  'app.clendan.com — the Clendan web application',
  'clendan.com — the marketing site',
]

const DO_NOT = [
  'Perform denial-of-service attacks or disrupt service for other users',
  'Use social engineering against Clendan staff or users',
  'Access, download, or modify data belonging to other users',
  'Perform physical attacks against infrastructure',
  'Attempt to compromise third-party services (Plaid, Xero, Clerk, etc.) via Clendan',
]

const CLENDAN_COMMITS = [
  'We will not pursue legal action for good-faith security research that follows this policy',
  'We will acknowledge your report within 48 hours',
  'We will provide a status update within 7 days of acknowledgement',
  'We will patch critical vulnerabilities within 90 days of confirmation',
  'We will credit you in our changelog when a fix ships (unless you prefer anonymity)',
]

const OUT_OF_SCOPE = [
  'Third-party services or integrations not under Clendan\'s control',
  'Physical attacks against data centres or infrastructure',
  'Social engineering of Clendan employees or contractors',
  'Issues in non-production or staging environments',
  'Spam or rate-limiting bypass without demonstrated security impact',
]

export default function SecurityPolicyPage() {
  return (
    <div className="flex flex-col min-h-screen bg-brand-bg">
      <Navbar />
      <main className="flex-1">
        <div className="max-w-3xl mx-auto px-6 md:px-8 pt-20 pb-24">
          <p className="font-body text-[11px] uppercase tracking-widest text-brand-muted mb-4">
            Security
          </p>
          <h1
            className="font-heading font-extrabold text-3xl md:text-4xl mb-2"
            style={{ fontFamily: 'var(--font-heading)' }}
          >
            Responsible Disclosure Policy
          </h1>
          <p className="font-body text-xs text-brand-muted mb-12">
            Last updated: 2026-06-05
          </p>

          {/* Scope */}
          <div className="border-t border-brand-border pt-10 mb-12">
            <h2
              className="font-heading font-bold text-xl mb-5"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              Scope
            </h2>
            <p className="font-body text-sm text-brand-secondary leading-relaxed mb-4">
              This policy applies to security vulnerabilities found in the following Clendan-owned
              systems:
            </p>
            <ul className="flex flex-col gap-3">
              {SCOPE_DOMAINS.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="text-brand-green font-body text-xs mt-0.5 shrink-0">—</span>
                  <span className="font-body text-sm text-brand-secondary leading-relaxed">
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* How to report */}
          <div className="border-t border-brand-border pt-10 mb-12">
            <h2
              className="font-heading font-bold text-xl mb-5"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              How to Report
            </h2>
            <p className="font-body text-sm text-brand-secondary leading-relaxed mb-4">
              Email{' '}
              <a
                href="mailto:security@clendan.com"
                className="text-brand-text hover:text-brand-green transition-colors"
              >
                security@clendan.com
              </a>{' '}
              with the following information:
            </p>
            <div className="bg-brand-surface border border-brand-border rounded-sm p-5">
              <ul className="flex flex-col gap-3">
                {[
                  'A clear description of the vulnerability',
                  'Step-by-step reproduction steps',
                  'The potential security impact if exploited',
                  'Any relevant screenshots, HTTP logs, or proof-of-concept code',
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <span className="text-brand-muted font-body text-xs mt-0.5 shrink-0">—</span>
                    <span className="font-body text-sm text-brand-secondary leading-relaxed">
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Response timeline */}
          <div className="border-t border-brand-border pt-10 mb-12">
            <h2
              className="font-heading font-bold text-xl mb-5"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              What Clendan Commits To
            </h2>
            <ul className="flex flex-col gap-3">
              {CLENDAN_COMMITS.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="text-brand-green font-body text-xs mt-0.5 shrink-0">—</span>
                  <span className="font-body text-sm text-brand-secondary leading-relaxed">
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Do not */}
          <div className="border-t border-brand-border pt-10 mb-12">
            <h2
              className="font-heading font-bold text-xl mb-5"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              What Researchers Must Not Do
            </h2>
            <ul className="flex flex-col gap-3">
              {DO_NOT.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span
                    className="font-body text-xs mt-0.5 shrink-0"
                    style={{ color: '#ff4d6d' }}
                  >
                    —
                  </span>
                  <span className="font-body text-sm text-brand-secondary leading-relaxed">
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Out of scope */}
          <div className="border-t border-brand-border pt-10">
            <h2
              className="font-heading font-bold text-xl mb-5"
              style={{ fontFamily: 'var(--font-heading)' }}
            >
              Out of Scope
            </h2>
            <ul className="flex flex-col gap-3">
              {OUT_OF_SCOPE.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="text-brand-muted font-body text-xs mt-0.5 shrink-0">—</span>
                  <span className="font-body text-sm text-brand-secondary leading-relaxed">
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
