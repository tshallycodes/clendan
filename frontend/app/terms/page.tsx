import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'

export const metadata = {
  title: 'Terms of Service — Clendan',
}

const SECTIONS = [
  {
    heading: 'Acceptance of Terms',
    body: [
      'By accessing or using Clendan, you agree to be bound by these Terms of Service.',
      'If you are using Clendan on behalf of a company, you represent that you have authority to bind that company to these terms.',
      'If you do not agree to these terms, do not use the service.',
    ],
  },
  {
    heading: 'Description of Service',
    body: [
      'Clendan is an AI Financial Agent OS — a platform for deploying autonomous AI tools that connect to financial systems, execute tasks, enforce policy, and produce audit trails.',
      'The service is provided as a subscription, billed monthly or annually.',
      'We reserve the right to modify or discontinue any part of the service with reasonable notice.',
    ],
  },
  {
    heading: 'User Obligations',
    body: [
      'You must provide accurate information when creating your account.',
      'You must not use Clendan for any unlawful purpose or in violation of any applicable financial regulations.',
      'You are responsible for maintaining the security of your account credentials and API keys.',
      'You must not attempt to access other tenants\' data or reverse-engineer the platform.',
      'You must not use the platform in a way that creates undue load or disrupts service for other users.',
    ],
  },
  {
    heading: 'Payment Terms',
    body: [
      'Subscriptions are billed monthly or annually in advance.',
      'All fees are non-refundable after the first 7 days of a new subscription period.',
      'We reserve the right to change pricing with 30 days\' notice to existing subscribers.',
      'Failure to pay may result in suspension or termination of your account.',
    ],
  },
  {
    heading: 'Intellectual Property',
    body: [
      'Clendan Ltd owns all intellectual property rights in the Clendan platform, including software, design, and documentation.',
      'You own all data you bring to the platform — your invoices, financial records, and documents remain yours.',
      'You grant Clendan a limited licence to process your data solely to provide the service.',
      'You may not copy, modify, or distribute the Clendan platform or its components.',
    ],
  },
  {
    heading: 'Limitation of Liability',
    body: [
      'The service is provided "as is" without warranty of any kind, express or implied.',
      'Clendan is not liable for financial decisions made by AI tools operating without human oversight.',
      'Human approval workflows exist for this reason — we strongly recommend enabling approval thresholds for high-value transactions.',
      'In no event shall Clendan\'s total liability exceed the fees paid by you in the three months preceding the claim.',
      'We are not liable for indirect, incidental, or consequential damages of any kind.',
    ],
  },
  {
    heading: 'Termination',
    body: [
      'Either party may terminate the agreement with 30 days\' written notice.',
      'We may terminate immediately if you breach these terms or engage in fraudulent activity.',
      'Upon termination, your access to the service will cease and your data will be deleted per our retention policy.',
    ],
  },
  {
    heading: 'Governing Law',
    body: [
      'These terms are governed by the laws of England and Wales.',
      'Any disputes shall be subject to the exclusive jurisdiction of the courts of England and Wales.',
    ],
  },
  {
    heading: 'Contact',
    body: ['For legal queries: legal@clendan.com', 'Clendan Ltd, England and Wales.'],
  },
]

export default function TermsPage() {
  return (
    <div className="flex flex-col min-h-screen bg-brand-bg">
      <Navbar />
      <main className="flex-1">
        <div className="max-w-3xl mx-auto px-6 md:px-8 pt-20 pb-24">
          <p className="font-body text-[10px] uppercase tracking-widest text-brand-muted mb-4">
            Legal
          </p>
          <h1
            className="font-heading font-extrabold text-3xl md:text-4xl mb-2"
            style={{ fontFamily: 'var(--font-heading)' }}
          >
            Terms of Service
          </h1>
          <p className="font-body text-xs text-brand-muted mb-12">
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
                      <span className="text-brand-muted font-body text-xs mt-0.5 shrink-0">—</span>
                      <span className="font-body text-sm text-brand-secondary leading-relaxed">
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
