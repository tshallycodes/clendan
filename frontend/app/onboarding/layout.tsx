import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'
import { getBackendToken } from '@/lib/auth'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default async function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth()
  if (!userId) redirect('/sign-in')

  // If already onboarded, skip straight to the dashboard
  try {
    const token = await getBackendToken()
    if (token) {
      const res = await fetch(`${API_BASE}/tenants/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      })
      if (res.ok) redirect('/dashboard')
    }
  } catch { /* backend down - let them through to complete onboarding */ }

  return <>{children}</>
}
