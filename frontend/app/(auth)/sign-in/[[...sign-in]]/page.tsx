import { SignIn } from '@clerk/nextjs'
import { Logo } from '@/components/Logo'

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center">
      <div className="flex flex-col items-center gap-8">
        <Logo size="lg" />
        <SignIn
          appearance={{
            variables: {
              colorBackground: '#111111',
              colorText: '#e8f0e8',
              colorPrimary: '#00C853',
              colorInputBackground: '#0a0a0a',
              colorInputText: '#e8f0e8',
              borderRadius: '4px',
            },
          }}
        />
      </div>
    </div>
  )
}
