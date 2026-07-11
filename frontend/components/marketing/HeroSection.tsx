'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { HeroTerminal } from './HeroTerminal'

const EASE: [number, number, number, number] = [0.25, 0.1, 0.25, 1]

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.13, delayChildren: 0.05 } },
}

const item = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } },
}

export function HeroSection() {
  return (
    <section
      className="relative flex flex-col items-center text-center px-6 md:px-8 pt-24 pb-16 overflow-hidden"
      style={{ minHeight: '90vh' }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(var(--brand-border) 1px, transparent 1px), linear-gradient(90deg, var(--brand-border) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          opacity: 0.6,
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% 0%, transparent 40%, var(--brand-bg) 100%)',
        }}
      />

      {/* Text content - staggered entrance */}
      <motion.div
        className="relative z-10 flex flex-col items-center max-w-4xl mx-auto w-full"
        variants={container}
        initial="hidden"
        animate="show"
      >
        <motion.p
          variants={item}
          className="text-xs font-body text-brand-muted uppercase tracking-widest mb-6"
        >
          The governed AI operator for finance teams
        </motion.p>

        <motion.h1
          variants={item}
          className="font-heading font-black leading-none tracking-tight text-brand-text mb-6"
          style={{ fontSize: 'clamp(40px, 7vw, 72px)' }}
        >
          Your Finance Ops,
          <br />
          <span style={{ color: '#00C853' }}>Run For You</span>
        </motion.h1>

        <motion.p
          variants={item}
          className="text-base font-body text-brand-secondary max-w-xl leading-relaxed mb-8"
        >
          Clendan operates the accounting software you already use — QuickBooks, Xero, Stripe,
          your bank. It reads your books, does the daily work inside them, and logs every action
          for you to defend. You sign off on anything that changes; it never moves money on its own.
        </motion.p>

        <motion.div variants={item} className="flex flex-col sm:flex-row items-center gap-3">
          <Link
            href="/sign-up"
            className="rounded-sm px-5 py-2.5 text-sm font-body font-medium transition-colors active:scale-[0.97]"
            style={{ background: '#00C853', color: '#000' }}
          >
            Connect your stack
          </Link>
          <Link
            href="/how-it-works"
            className="border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-5 py-2.5 text-sm font-body transition-colors"
          >
            See How It Works
          </Link>
        </motion.div>
      </motion.div>

      {/* Terminal - completely outside variants so the float CSS animation runs unimpeded */}
      <motion.div
        className="relative z-10 w-full max-w-4xl mx-auto"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.55, ease: EASE }}
      >
        <HeroTerminal />
      </motion.div>
    </section>
  )
}
