import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'
import { HeroTerminal } from '@/components/marketing/HeroTerminal'
import { SocialProofStrip, ProblemStatement, SolutionOverview, CTABanner } from '@/components/marketing/LandingSections'
import { HowItWorks } from '@/components/marketing/HowItWorks'
import { WorkerShowcase } from '@/components/marketing/WorkerShowcase'

export default async function HomePage() {
  // Guard: auth() throws when Clerk keys are not configured (proxy.ts dev fallback).
  const hasClerk = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith('pk_')
  if (hasClerk) {
    const { userId } = await auth()
    if (userId) redirect('/onboarding')
  }

  return (
    <div className="flex flex-col min-h-screen bg-brand-bg">
      <Navbar />
      <main className="flex-1">
        <HeroSection />
        <SocialProofStrip />
        <ProblemStatement />
        <SolutionOverview />
        <HowItWorks />
        <WorkerShowcase />
        <CTABanner />
      </main>
      <Footer />
    </div>
  )
}

function HeroSection() {
  return (
    <section
      className="relative flex flex-col items-center text-center px-6 md:px-8 pt-24 pb-16 overflow-hidden"
      style={{ minHeight: '90vh' }}
    >
      {/* Grid background */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(26,42,26,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(26,42,26,0.35) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />
      {/* Radial fade so grid fades to bg at edges */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% 0%, transparent 40%, #0a0a0f 100%)',
        }}
      />

      <div className="relative z-10 flex flex-col items-center max-w-4xl mx-auto">
        <p className="text-xs font-mono text-brand-muted uppercase tracking-widest mb-6">
          AI Financial Agent OS
        </p>

        <h1
          className="font-heading font-black leading-none tracking-tight text-brand-text mb-6"
          style={{ fontSize: 'clamp(40px, 7vw, 72px)' }}
        >
          Your Finance Team,
          <br />
          <span style={{ color: '#00C853' }}>Running on Autopilot</span>
        </h1>

        <p className="text-base font-mono text-brand-secondary max-w-xl leading-relaxed mb-8">
          Deploy AI workers that connect to your financial systems, execute tasks autonomously,
          and produce full audit trails for every action. Not a dashboard. Execution infrastructure.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-3">
          <Link
            href="/sign-up"
            className="rounded-sm px-5 py-2.5 text-sm font-mono font-medium transition-colors"
            style={{ background: '#00C853', color: '#000' }}
          >
            Deploy Your First Worker
          </Link>
          <Link
            href="/how-it-works"
            className="border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-5 py-2.5 text-sm font-mono transition-colors"
          >
            See How It Works
          </Link>
        </div>

        <HeroTerminal />
      </div>
    </section>
  )
}
