import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { Sidebar } from '@/components/dashboard/Sidebar'
import { MobileNav } from '@/components/dashboard/MobileNav'
import { ClenDashboard } from '@/components/clen/ClenDashboard'
import { getBackendToken } from '@/lib/auth'

const API_BASE = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth()
  if (!userId) redirect('/sign-in')

  let backendStatus: 'ok' | 'not_onboarded' | 'unreachable' = 'unreachable'

  try {
    const token = await getBackendToken()
    if (token) {
      const res = await fetch(`${API_BASE}/v1/tenants/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      })
      if (res.status === 404 || res.status === 403 || res.status === 401) {
        backendStatus = 'not_onboarded'
      } else if (res.ok) {
        backendStatus = 'ok'
      }
    }
  } catch { /* backend unreachable */ }

  if (backendStatus === 'not_onboarded') redirect('/onboarding')

  return (
    <div className="flex min-h-screen bg-brand-bg">
      <Sidebar />
      <MobileNav />
      <div className="flex-1 overflow-auto flex flex-col pt-[57px] lg:pt-0">
        {backendStatus === 'unreachable' && (
          <div className="bg-[rgba(245,166,35,0.08)] border-b border-[rgba(245,166,35,0.2)] px-6 py-2.5 flex items-center justify-between">
            <p className="text-[11px] font-mono text-[#f5a623]">
              Backend not reachable — start the FastAPI server to see live data
            </p>
            <Link href="/onboarding" className="text-[11px] font-mono text-[#f5a623] underline underline-offset-2 hover:opacity-80">
              Complete onboarding →
            </Link>
          </div>
        )}
        <main className="flex-1">{children}</main>
      </div>
      <div className="fixed bottom-6 right-6 z-30">
        <ClenDashboard />
      </div>
    </div>
  )
}
