import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'
import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'
import { HeroSection } from '@/components/marketing/HeroSection'
import { SocialProofStrip, ProblemStatement, SolutionOverview, CTABanner } from '@/components/marketing/LandingSections'
import { HowItWorks } from '@/components/marketing/HowItWorks'
import { WorkerShowcase } from '@/components/marketing/WorkerShowcase'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'

interface OnboardingStatus {
  onboarding_complete: boolean
  org_provisioned: boolean
}

export default async function HomePage() {
  const hasClerk = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith('pk_')
  if (hasClerk) {
    const { userId } = await auth()
    if (userId) {
      try {
        const token = await getBackendToken()
        if (token) {
          const status = await apiGet<OnboardingStatus>('/v1/onboarding/status', token)
          redirect(status.onboarding_complete ? '/dashboard' : '/onboarding')
        }
      } catch {
        // Backend unreachable or user has no tenant yet — send to onboarding
      }
      redirect('/onboarding')
    }
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
