import { Logo } from '@/components/Logo'
import { AuthSignIn } from '@/components/auth/AuthCard'

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center">
      <div className="flex flex-col items-center gap-8">
        <Logo size="lg" />
        <AuthSignIn />
      </div>
    </div>
  )
}
