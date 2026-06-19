import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'
import { Sidebar } from '@/components/dashboard/Sidebar'
import { MobileNav } from '@/components/dashboard/MobileNav'
import { ClenDashboard } from '@/components/clen/ClenDashboard'
import { getBackendToken } from '@/lib/auth'

const API_BASE = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth()
  if (!userId) redirect('/sign-in')

  let needsOnboarding = false
  try {
    const token = await getBackendToken()
    if (token) {
      const res = await fetch(`${API_BASE}/v1/tenants/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      })
      if (res.status === 404 || res.status === 403) needsOnboarding = true
    }
  } catch { /* backend unreachable — proceed to dashboard */ }
  if (needsOnboarding) redirect('/onboarding')

  return (
    <div className="flex min-h-screen bg-brand-bg">
      <Sidebar />
      <MobileNav />
      <div className="flex-1 overflow-auto flex flex-col pt-[57px] lg:pt-0">
        <main className="flex-1">{children}</main>
      </div>
      <div className="fixed bottom-6 right-6 z-30">
        <ClenDashboard />
      </div>
    </div>
  )
}
