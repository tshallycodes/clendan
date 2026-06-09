import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'
import { HeroSection } from '@/components/marketing/HeroSection'
import { SocialProofStrip, ProblemStatement, SolutionOverview, CTABanner } from '@/components/marketing/LandingSections'
import { HowItWorks } from '@/components/marketing/HowItWorks'
import { WorkerShowcase } from '@/components/marketing/WorkerShowcase'

export default function HomePage() {
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
