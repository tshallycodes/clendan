'use client'

import Link from 'next/link'
import { Lightning, Link, ShieldCheck } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import { FadeInUp, StaggerContainer, StaggerItem } from './AnimationWrappers'

// ─── Social Proof Strip ────────────────────────────────────────────────────

const INTEGRATIONS = ['Xero', 'QuickBooks', 'Plaid', 'Stripe', 'NetSuite', 'Salesforce']
const MARQUEE_ITEMS = [...INTEGRATIONS, ...INTEGRATIONS]

export function SocialProofStrip() {
  return (
    <div className="border-y border-brand-border bg-brand-surface overflow-hidden">
      <div className="py-5 flex items-center gap-6">
        <span className="text-xs font-mono text-brand-muted shrink-0 pl-6 md:pl-8">
          Trusted integrations with:
        </span>
        <div className="flex items-center overflow-hidden flex-1 min-w-0">
          <div className="flex items-center gap-10 shrink-0" style={{ animation: 'marquee 18s linear infinite' }}>
            {MARQUEE_ITEMS.map((name, i) => (
              <span key={i} className="text-sm font-mono text-brand-muted shrink-0">
                {name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Problem Statement ─────────────────────────────────────────────────────

const STATS = [
  { figure: '66%', claim: 'of AP teams still process invoices manually', source: 'Ardent Partners 2025' },
  { figure: '50%', claim: 'of finance teams take 6+ days to close the books each month', source: 'Ledge 2025' },
  { figure: '$6+', claim: 'average cost to manually process a single invoice', source: 'industry average' },
]

export function ProblemStatement() {
  return (
    <section className="max-w-6xl mx-auto px-6 md:px-8 py-20">
      <FadeInUp>
        <h2 className="font-heading text-2xl font-bold text-brand-text mb-8">Finance Operations Are Broken</h2>
      </FadeInUp>
      <StaggerContainer className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {STATS.map((s) => (
          <StaggerItem key={s.figure}>
            <motion.div
              className="bg-brand-surface rounded-sm p-6 flex flex-col gap-3 h-full border border-brand-border"
              whileHover={{ borderColor: 'rgba(0,200,83,0.35)', y: -2 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
            >
              <span className="font-heading text-4xl font-bold" style={{ color: '#00C853' }}>{s.figure}</span>
              <p className="text-sm font-mono text-brand-secondary leading-relaxed">{s.claim}</p>
              <span className="text-xs font-mono text-brand-muted mt-auto">{s.source}</span>
            </motion.div>
          </StaggerItem>
        ))}
      </StaggerContainer>
    </section>
  )
}

// ─── Solution Overview ─────────────────────────────────────────────────────

const SOLUTIONS = [
  { icon: Lightning, title: 'Deploy AI Tools', desc: 'Autonomous agents that execute real financial tasks, not just surface insights.' },
  { icon: Link, title: 'Connect Your Stack', desc: 'Native integrations with Xero, QuickBooks, Plaid, Stripe, and your ERP.' },
  { icon: ShieldCheck, title: 'Full Audit Trail', desc: 'Every action logged, every decision explained. Policy-enforced by default.' },
]

export function SolutionOverview() {
  return (
    <section className="border-y border-brand-border bg-brand-surface">
      <div className="max-w-6xl mx-auto px-6 md:px-8 py-20">
        <FadeInUp>
          <h2 className="font-heading text-xl font-bold text-brand-text mb-2 max-w-2xl">
            Deploy AI Tools. Connect Your Stack. Execute With a Full Audit Trail.
          </h2>
          <p className="text-sm font-mono text-brand-muted mb-10">Infrastructure, not a dashboard.</p>
        </FadeInUp>
        <StaggerContainer className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SOLUTIONS.map(({ icon: Icon, title, desc }) => (
            <StaggerItem key={title}>
              <motion.div
                className="bg-brand-bg rounded-sm p-6 flex flex-col gap-4 h-full border border-brand-border"
                whileHover={{ borderColor: 'rgba(0,200,83,0.25)', y: -2 }}
                transition={{ duration: 0.15, ease: 'easeOut' }}
              >
                <Icon size={18} className="text-brand-secondary" />
                <div>
                  <h3 className="font-heading text-sm font-semibold text-brand-text mb-1">{title}</h3>
                  <p className="text-xs font-mono text-brand-muted leading-relaxed">{desc}</p>
                </div>
              </motion.div>
            </StaggerItem>
          ))}
        </StaggerContainer>
      </div>
    </section>
  )
}

// ─── CTA Banner ────────────────────────────────────────────────────────────

export function CTABanner() {
  return (
    <section className="max-w-6xl mx-auto px-6 md:px-8 py-20">
      <FadeInUp>
        <div
          className="rounded-sm p-10 md:p-14 text-center flex flex-col items-center gap-6 bg-brand-surface"
          style={{ border: '1px solid rgba(0,200,83,0.2)' }}
        >
          <h2 className="font-heading text-3xl md:text-4xl font-bold text-brand-text">
            Ready to Automate Your Finance Stack?
          </h2>
          <p className="text-sm font-mono text-brand-secondary max-w-sm">
            Deploy your first AI tool in under 10 minutes.
          </p>
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} transition={{ duration: 0.15 }}>
            <Link
              href="/sign-up"
              className="rounded-sm px-6 py-3 text-sm font-mono font-medium transition-colors inline-block"
              style={{ background: '#00C853', color: '#000' }}
            >
              Request Early Access
            </Link>
          </motion.div>
        </div>
      </FadeInUp>
    </section>
  )
}
