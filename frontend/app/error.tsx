'use client'

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[Clendan]', error)
  }, [error])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-brand-bg text-brand-text px-6 text-center">
      <p
        className="font-heading font-bold text-2xl mb-3"
        style={{ fontFamily: 'var(--font-heading)' }}
      >
        Something went wrong.
      </p>

      <p className="font-body text-sm text-brand-muted mb-8">
        Our team has been notified automatically.
      </p>

      <button
        onClick={reset}
        className="rounded-sm px-6 py-3 text-sm font-body font-medium mb-6 transition-colors hover:bg-[#00a844]"
        style={{ background: '#00C853', color: '#000' }}
      >
        Try again
      </button>

      <p className="font-body text-xs text-brand-muted">
        If this keeps happening, contact{' '}
        <a
          href="mailto:support@clendan.com"
          className="text-brand-secondary hover:text-brand-text transition-colors underline underline-offset-2"
        >
          support@clendan.com
        </a>
      </p>

      {error.digest && (
        <p className="font-body text-[11px] text-brand-muted mt-4">
          Digest: {error.digest}
        </p>
      )}
    </div>
  )
}
