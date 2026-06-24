import { SignUp } from '@clerk/nextjs'
import { Logo } from '@/components/Logo'
import { clerkDarkAppearance } from '@/lib/clerk-appearance'

export default function SignUpPage() {
  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center">
      <div className="flex flex-col items-center gap-8">
        <Logo size="lg" />
        <SignUp appearance={clerkDarkAppearance} />
      </div>
    </div>
  )
}
