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

      <motion.div
        className="relative z-10 flex flex-col items-center max-w-4xl mx-auto"
        variants={container}
        initial="hidden"
        animate="show"
      >
        <motion.p
          variants={item}
          className="text-xs font-mono text-brand-muted uppercase tracking-widest mb-6"
        >
          AI Financial Agent OS
        </motion.p>

        <motion.h1
          variants={item}
          className="font-heading font-black leading-none tracking-tight text-brand-text mb-6"
          style={{ fontSize: 'clamp(40px, 7vw, 72px)' }}
        >
          Your Finance Team,
          <br />
          <span style={{ color: '#00C853' }}>Running on Autopilot</span>
        </motion.h1>

        <motion.p
          variants={item}
          className="text-base font-mono text-brand-secondary max-w-xl leading-relaxed mb-8"
        >
          Deploy AI tools that connect to your financial systems, execute tasks autonomously,
          and produce full audit trails for every action. Not a dashboard. Execution infrastructure.
        </motion.p>

        <motion.div variants={item} className="flex flex-col sm:flex-row items-center gap-3">
          <Link
            href="/sign-up"
            className="rounded-sm px-5 py-2.5 text-sm font-mono font-medium transition-colors active:scale-[0.97]"
            style={{ background: '#00C853', color: '#000' }}
          >
            Deploy Your First Tool
          </Link>
          <Link
            href="/how-it-works"
            className="border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-5 py-2.5 text-sm font-mono transition-colors"
          >
            See How It Works
          </Link>
        </motion.div>

        <motion.div variants={item} className="w-full">
          <HeroTerminal />
        </motion.div>
      </motion.div>
    </section>
  )
}
