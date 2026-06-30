'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useUser, useAuth } from '@clerk/nextjs'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface LinkInfo {
  org_name: string
  role: string
  expires_at: string
}

type PageState = 'loading' | 'ready' | 'not_found' | 'expired' | 'accepting' | 'done' | 'error'

const ROLE_LABEL: Record<string, string> = {
  admin: 'Admin',
  approver: 'Approver',
  viewer: 'Viewer',
}

const BTN_PRIMARY = 'block w-full text-center bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97] rounded-sm px-4 py-2.5 text-xs font-body font-medium transition-all disabled:opacity-60 disabled:cursor-not-allowed'
const BTN_SECONDARY = 'block w-full text-center bg-transparent border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-4 py-2.5 text-xs font-body font-medium transition-all'

export default function JoinPage() {
  const params = useParams()
  const token = params?.token as string | undefined
  const { isLoaded, isSignedIn } = useUser()
  const { getToken } = useAuth()
  const router = useRouter()
  const [info, setInfo] = useState<LinkInfo | null>(null)
  const [pageState, setPageState] = useState<PageState>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!token) return
    fetch(`${API}/organisations/join/${token}`)
      .then(async (res) => {
        if (res.status === 404) return setPageState('not_found')
        if (res.status === 410) return setPageState('expired')
        if (!res.ok) { setErrorMsg('Failed to load invitation'); return setPageState('error') }
        const body = await res.json()
        setInfo(body.data)
        setPageState('ready')
      })
      .catch(() => { setErrorMsg('Unable to connect to server'); setPageState('error') })
  }, [token])

  async function accept() {
    setPageState('accepting')
    try {
      const authToken = await getToken()
      const res = await fetch(`${API}/organisations/join/${token}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail ?? 'Failed to accept invitation')
      }
      setPageState('done')
      setTimeout(() => router.push('/dashboard'), 1500)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to accept invitation')
      setPageState('error')
    }
  }

  const returnUrl = encodeURIComponent(`/join/${token}`)

  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center p-6">
      <div className="w-full max-w-sm flex flex-col items-center gap-8">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 border border-[#00C853] flex items-center justify-center font-bold text-[#00C853] font-body text-sm">C</div>
          <span className="text-brand-text font-bold tracking-widest uppercase text-sm" style={{ fontFamily: 'var(--font-heading, sans-serif)' }}>Clendan</span>
        </div>

        <div className="w-full bg-brand-surface border border-brand-border rounded-sm p-6 space-y-5">
          {pageState === 'loading' && (
            <div className="space-y-3 animate-pulse py-2">
              <div className="h-4 bg-brand-elevated rounded-sm w-3/4" />
              <div className="h-3 bg-brand-elevated rounded-sm w-1/2" />
              <div className="h-9 bg-brand-elevated rounded-sm mt-4" />
            </div>
          )}

          {pageState === 'not_found' && (
            <StatusMessage icon="✕" title="Link not found" body="This invite link doesn't exist or has been revoked." danger />
          )}

          {pageState === 'expired' && (
            <StatusMessage icon="⊘" title="Link expired" body="This invite link has expired. Ask your admin to generate a new one." danger />
          )}

          {pageState === 'error' && (
            <StatusMessage icon="✕" title="Something went wrong" body={errorMsg} danger />
          )}

          {pageState === 'done' && (
            <StatusMessage icon="✓" title="You're in!" body="Redirecting to your dashboard…" />
          )}

          {(pageState === 'ready' || pageState === 'accepting') && info && (
            <>
              <div className="space-y-2">
                <p className="text-[11px] font-body text-brand-muted uppercase tracking-widest">You've been invited to</p>
                <h1 className="text-xl font-bold text-brand-text" style={{ fontFamily: 'var(--font-heading, sans-serif)' }}>
                  {info.org_name}
                </h1>
                <div className="flex items-center gap-2 pt-0.5">
                  <span className="text-[11px] font-body text-brand-muted uppercase tracking-widest">Role</span>
                  <span className="text-[11px] font-body font-medium px-2 py-0.5 rounded-sm bg-brand-elevated border border-brand-border text-brand-text uppercase tracking-wider">
                    {ROLE_LABEL[info.role] ?? info.role}
                  </span>
                </div>
              </div>

              {!isLoaded ? (
                <div className="h-9 bg-brand-elevated rounded-sm animate-pulse" />
              ) : isSignedIn ? (
                <button onClick={accept} disabled={pageState === 'accepting'} className={BTN_PRIMARY}>
                  {pageState === 'accepting' ? 'Joining…' : 'Accept invitation'}
                </button>
              ) : (
                <div className="space-y-2">
                  <Link href={`/sign-up?redirect_url=${returnUrl}`} className={BTN_PRIMARY}>
                    Create account to accept
                  </Link>
                  <Link href={`/sign-in?redirect_url=${returnUrl}`} className={BTN_SECONDARY}>
                    Sign in instead
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusMessage({ icon, title, body, danger = false }: {
  icon: string
  title: string
  body: string
  danger?: boolean
}) {
  return (
    <div className="text-center space-y-2 py-2">
      <p className="text-2xl font-body" style={{ color: danger ? '#ff4d6d' : '#00C853' }}>{icon}</p>
      <p className="text-sm font-bold text-brand-text" style={{ fontFamily: 'var(--font-heading, sans-serif)' }}>{title}</p>
      <p className="text-xs font-body text-brand-muted leading-relaxed">{body}</p>
    </div>
  )
}
