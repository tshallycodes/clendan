import Link from 'next/link'

const LINKS = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Workers', href: '/workers' },
  { label: 'Pricing', href: '/pricing' },
  { label: 'Docs', href: '/docs' },
]

export default function NotFound() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center bg-brand-bg text-brand-text px-6"
    >
      <span
        className="font-heading font-black leading-none select-none"
        style={{
          fontFamily: 'var(--font-heading)',
          fontSize: 120,
          color: '#00C853',
          fontWeight: 900,
          lineHeight: 1,
        }}
      >
        404
      </span>

      <p className="font-mono text-base text-brand-text mt-4 mb-10">
        This page doesn&apos;t exist.
      </p>

      <div className="flex flex-wrap gap-3 justify-center mb-10">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-4 py-2 text-sm font-mono transition-colors"
          >
            {link.label}
          </Link>
        ))}
      </div>

      <Link
        href="/"
        className="rounded-sm px-6 py-3 text-sm font-mono font-medium transition-colors hover:bg-[#00a844]"
        style={{ background: '#00C853', color: '#000' }}
      >
        ← Back to home
      </Link>
    </div>
  )
}
