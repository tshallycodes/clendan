import { Logo } from '@/components/Logo'

export const metadata = {
  title: 'Maintenance — Clendan',
}

export default function MaintenancePage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-brand-bg text-brand-text px-6 text-center">
      <div className="mb-10">
        <Logo size="lg" href={null} />
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
