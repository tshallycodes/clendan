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
    console.error('[Clendan Error Boundary]', error)
  }, [error])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-brand-bg text-brand-text px-6 text-center">
      <p
        className="font-heading font-bold text-2xl mb-3"
        style={{ fontFamily: 'var(--font-heading)' }}
      >
        Something went wrong.
      </p>

      <p className="font-mono text-sm text-brand-muted mb-8">
        Our team has been notified automatically.
      </p>

      <button
        onClick={reset}
        className="rounded-sm px-6 py-3 text-sm font-mono font-medium mb-6 transition-colors hover:bg-[#00a844]"
        style={{ background: '#00C853', color: '#000' }}
      >
        Try again
      </button>

      {(error.message || error.digest) && (
        <div className="mb-6 max-w-xl w-full text-left bg-brand-elevated border border-brand-border rounded-sm p-4">
          {error.message && (
            <p className="font-mono text-xs text-[#ff4d6d] break-all">{error.message}</p>
          )}
          {error.stack && (
            <pre className="font-mono text-[10px] text-brand-muted mt-2 overflow-auto max-h-48 whitespace-pre-wrap break-all">
              {error.stack}
            </pre>
          )}
          {error.digest && (
            <p className="font-mono text-[10px] text-brand-muted mt-2">Digest: {error.digest}</p>
          )}
        </div>
      )}

      <p className="font-mono text-xs text-brand-muted">
        If this keeps happening, contact{' '}
        <a
          href="mailto:support@clendan.com"
          className="text-brand-secondary hover:text-brand-text transition-colors underline underline-offset-2"
        >
          support@clendan.com
        </a>
      </p>
    </div>
  )
}
