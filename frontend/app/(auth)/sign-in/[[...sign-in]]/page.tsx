import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center">
      <div className="flex flex-col items-center gap-8">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 border border-brand-green flex items-center justify-center font-bold text-brand-green font-mono text-sm">C</div>
          <span className="text-brand-text font-bold tracking-widest uppercase text-sm font-heading">Clendan</span>
        </div>
        <SignIn
          appearance={{
            variables: {
              colorBackground: '#111118',
              colorText: '#e8f0e8',
              colorPrimary: '#00C853',
              colorInputBackground: '#0a0a0f',
              colorInputText: '#e8f0e8',
              borderRadius: '4px',
            },
          }}
        />
      </div>
    </div>
  )
}
