export const metadata = {
  title: 'Maintenance — Clendan',
}

function LogoMark() {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="flex items-center justify-center"
        style={{ width: 32, height: 32, border: '1px solid #00C853', borderRadius: 2 }}
      >
        <span
          style={{
            fontFamily: 'var(--font-heading)',
            fontWeight: 800,
            fontSize: 16,
            color: '#00C853',
          }}
        >
          C
        </span>
      </div>
      <span
        style={{
          fontFamily: 'var(--font-heading)',
          fontWeight: 700,
          fontSize: 13,
          letterSpacing: '0.18em',
          color: '#e8f0e8',
        }}
      >
        CLENDAN
      </span>
    </div>
  )
}

export default function MaintenancePage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-brand-bg text-brand-text px-6 text-center">
      <div className="mb-10">
        <LogoMark />
      </div>

      <h1
        className="font-heading font-bold text-2xl mb-3"
        style={{ fontFamily: 'var(--font-heading)' }}
      >
        Clendan is under scheduled maintenance
      </h1>

      <p className="font-mono text-sm text-brand-secondary mb-6 max-w-sm">
        We&apos;ll be back online shortly. Follow{' '}
        <a
          href="https://x.com/clendan"
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand-text hover:text-brand-green transition-colors"
        >
          @clendan
        </a>{' '}
        for updates.
      </p>

      <div className="bg-brand-surface border border-brand-border rounded-sm px-5 py-3 font-mono text-xs text-brand-muted">
        Expected back: soon
      </div>
    </div>
  )
}
