'use client'

import { useState } from 'react'

interface FAQItem {
  q: string
  a: string
}

const FAQ_ITEMS: FAQItem[] = [
  {
    q: 'What counts as an execution?',
    a: 'Any time a tool processes a document or makes a financial decision. This includes invoice processing, payment approvals, reconciliation checks, and policy evaluations.',
  },
  {
    q: 'Can I build custom tools?',
    a: 'Enterprise plan includes custom tool development with our team. We work directly with your engineering team to build tools that map to your specific financial workflows and systems.',
  },
  {
    q: 'How does the audit trail work?',
    a: 'Every action written to an immutable, append-only log. No UPDATE, no DELETE — ever. The audit trail records the tool version, input data, policy evaluation, output, and full reasoning trace. Can be exported as CSV or JSON at any time.',
  },
  {
    q: 'Is my financial data encrypted?',
    a: 'Yes. AES-256 at rest, TLS 1.3 in transit. Credentials are never stored in plaintext. OAuth tokens and API keys are encrypted with tenant-specific keys and never appear in logs or API responses.',
  },
  {
    q: 'Can I switch plans at any time?',
    a: 'Yes. Upgrades are immediate — new limits apply instantly. Downgrades take effect at the next billing cycle. You keep access to current plan features until the cycle ends.',
  },
]

export function PricingFAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  return (
    <div className="space-y-2 max-w-3xl">
      {FAQ_ITEMS.map((item, i) => {
        const isOpen = openIndex === i
        return (
          <div key={i} className="bg-brand-surface border border-brand-border rounded-sm overflow-hidden">
            <button
              onClick={() => setOpenIndex(isOpen ? null : i)}
              className="w-full flex items-center justify-between px-5 py-4 text-left gap-4 hover:bg-brand-elevated transition-colors"
              aria-expanded={isOpen}
            >
              <span className="font-heading font-semibold text-[16px] text-brand-text">
                {item.q}
              </span>
              <span
                className={`flex-shrink-0 font-mono text-[18px] text-brand-muted transition-transform duration-200 ${
                  isOpen ? 'rotate-45' : ''
                }`}
              >
                +
              </span>
            </button>
            {isOpen && (
              <div className="px-5 pb-4 border-t border-brand-border pt-4">
                <p className="font-mono text-[13px] text-brand-secondary leading-relaxed">
                  {item.a}
                </p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
