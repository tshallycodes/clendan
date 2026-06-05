import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0a0f]">
      <SignIn forceRedirectUrl="/dashboard" fallbackRedirectUrl="/dashboard" signUpUrl="/sign-up" />
    </main>
  )
}
