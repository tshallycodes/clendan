'use client'

import { Suspense, useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function DropboxExchange() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const called = useRef(false)

  useEffect(() => {
    if (called.current) return
    called.current = true

    const code = searchParams.get('code')
    const state = searchParams.get('state')

    if (!code || !state) {
      router.replace('/dashboard/integrations?error=dropbox')
      return
    }

    const params = new URLSearchParams({ code, state })
    fetch(`${API}/integrations/dropbox/exchange?${params}`)
      .then(res => {
        router.replace(res.ok
          ? '/dashboard/integrations?connected=dropbox'
          : '/dashboard/integrations?error=dropbox'
        )
      })
      .catch(() => router.replace('/dashboard/integrations?error=dropbox'))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}

export default function DropboxCallbackPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-bg">
      <div className="text-center space-y-3">
        <div className="w-5 h-5 border-2 border-[#0061FF] border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-xs font-mono text-brand-muted">Connecting Dropbox…</p>
        <Suspense>
          <DropboxExchange />
        </Suspense>
      </div>
    </div>
  )
}
