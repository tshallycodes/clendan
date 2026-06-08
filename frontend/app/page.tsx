import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'
import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'
import { HeroSection } from '@/components/marketing/HeroSection'
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
