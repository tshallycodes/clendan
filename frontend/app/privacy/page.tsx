import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'

export const metadata = {
  title: 'Privacy Policy — Clendan',
}

const SECTIONS = [
  {
    heading: 'What Data We Collect',
    body: [
      'Email address and company name, collected at signup.',
      'Financial document data (invoices, receipts, statements) processed on your behalf as part of the Clendan service.',
      'Usage data and agent execution logs, used to provide and improve the service.',
      'Authentication data managed via Clerk — we do not store raw passwords.',
    ],
  },
  {
    heading: 'How We Use It',
    body: [
      'To provide, operate, and improve the Clendan platform.',
      'To process financial documents and execute agent tasks on your behalf.',
      'To send you product updates and security notices (you can opt out of marketing at any time).',
      'We do not use your financial data to train AI models.',
    ],
  },
  {
    heading: 'Who We Share It With',
    body: [
      'Anthropic — for AI processing of agent tasks. Subject to Anthropic\'s data processing terms.',
      'Railway — for infrastructure hosting in the UK/EU region.',
      'Clerk — for authentication and session management.',
      'We do not sell your data to any third party. Ever.',
    ],
  },
  {
    heading: 'Data Retention',
    body: [
      'Account data: retained until you delete your account.',
      'Audit logs: retained per your plan tier. See your plan details.',
      'Processed financial documents: purged after 30 days.',
      'Application logs: retained for 90 days for operational purposes.',
    ],
  },
  {
    heading: 'Your Rights',
    body: [
      'Access: request a copy of all data we hold about you.',
      'Erasure: request deletion of your account and associated data.',
      'Portability: export your data in a machine-readable format.',
      'Rectification: correct inaccurate personal data.',
      'To exercise any right, email privacy@clendan.com. We respond within 30 days.',
    ],
  },
  {
    heading: 'Cookie Policy',
    body: [
      'We use essential cookies only — session management and authentication.',
      'We do not use advertising cookies or third-party tracking cookies.',
      'You can disable cookies in your browser, but this will prevent you from logging in.',
    ],
  },
  {
    heading: 'Contact',
    body: [
      'For privacy-related questions or to exercise your rights: privacy@clendan.com',
      'Clendan Ltd, England and Wales.',
    ],
  },
]

export default function PrivacyPage() {
  return (
    <div className="flex flex-col min-h-screen bg-brand-bg">
      <Navbar />
      <main className="flex-1">
        <div className="max-w-3xl mx-auto px-6 md:px-8 pt-20 pb-24">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">
            Legal
          </p>
          <h1
            className="font-heading font-extrabold text-3xl md:text-4xl mb-2"
            style={{ fontFamily: 'var(--font-heading)' }}
          >
            Privacy Policy
          </h1>
          <p className="font-mono text-xs text-brand-muted mb-12">
            Last updated: 2026-06-05
          </p>

          <div className="flex flex-col gap-12">
            {SECTIONS.map((section) => (
              <div key={section.heading} className="border-t border-brand-border pt-10">
                <h2
                  className="font-heading font-bold text-xl mb-5"
                  style={{ fontFamily: 'var(--font-heading)' }}
                >
                  {section.heading}
                </h2>
                <ul className="flex flex-col gap-3">
                  {section.body.map((item, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <span className="text-brand-muted font-mono text-xs mt-0.5 shrink-0">—</span>
                      <span className="font-mono text-sm text-brand-secondary leading-relaxed">
                        {item}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
