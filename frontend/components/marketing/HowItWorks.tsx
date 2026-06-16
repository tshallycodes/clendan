'use client'

import { motion } from 'framer-motion'
import { FadeInUp, StaggerContainer, StaggerItem } from './AnimationWrappers'

const STEPS = [
  { num: '01', title: 'Connect', desc: 'Link your bank, ERP, and accounting tools via OAuth in minutes.' },
  { num: '02', title: 'Configure', desc: 'Set policy rules, approval thresholds, and tool permissions.' },
  { num: '03', title: 'Execute', desc: 'Tools run autonomously, enforcing policy on every action.' },
  { num: '04', title: 'Monitor', desc: 'Full audit trail. Every decision, every outcome, every trace ID.' },
]

export function HowItWorks() {
  return (
    <section className="max-w-6xl mx-auto px-6 md:px-8 py-20">
      <FadeInUp>
        <p className="text-xs font-mono text-brand-muted uppercase tracking-widest mb-3">How it works</p>
        <h2 className="font-heading text-2xl font-bold text-brand-text mb-12">
          From Invoice to Payment in Under 30 Seconds
        </h2>
      </FadeInUp>

      <div className="relative">
        {/* Animated connector line — desktop only */}
        <motion.div
          className="hidden md:block absolute top-6 left-0 right-0 h-px border-t border-dashed border-brand-border"
          style={{ transformOrigin: 'left', zIndex: 0 }}
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.9, ease: [0.25, 0.1, 0.25, 1], delay: 0.2 }}
          aria-hidden
        />

        <StaggerContainer
          className="grid grid-cols-1 md:grid-cols-4 gap-8 relative z-10"
          delay={0.3}
        >
          {STEPS.map((step) => (
            <StaggerItem key={step.num}>
              <div className="flex flex-col gap-4">
                <motion.div
                  className="w-12 h-12 flex items-center justify-center rounded-sm shrink-0 bg-brand-bg border border-brand-border"
                  whileHover={{ borderColor: 'rgba(0,200,83,0.4)', scale: 1.05 }}
                  transition={{ duration: 0.15 }}
                >
                  <span className="font-heading text-sm font-bold" style={{ color: '#00C853' }}>
                    {step.num}
                  </span>
                </motion.div>
                <div>
                  <h3 className="font-heading text-sm font-semibold text-brand-text mb-1.5">{step.title}</h3>
                  <p className="text-xs font-mono text-brand-muted leading-relaxed">{step.desc}</p>
                </div>
              </div>
            </StaggerItem>
          ))}
        </StaggerContainer>
      </div>
    </section>
  )
}
