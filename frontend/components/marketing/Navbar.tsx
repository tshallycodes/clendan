'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { ThemeToggle } from '@/components/ThemeToggle'

const NAV_LINKS = [
  { label: 'How It Works', href: '/how-it-works' },
  { label: 'Workers', href: '/workers' },
  { label: 'API Tools', href: '/api-tools' },
  { label: 'Pricing', href: '/pricing' },
]

function LogoMark() {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="flex items-center justify-center"
        style={{
          width: 28,
          height: 28,
          border: '1px solid #00C853',
          borderRadius: 2,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-syne)',
            fontWeight: 800,
            fontSize: 14,
            color: '#00C853',
            lineHeight: 1,
          }}
        >
          C
        </span>
      </div>
      <span
        style={{
          fontFamily: 'var(--font-syne)',
          fontWeight: 700,
          fontSize: 13,
          letterSpacing: '0.18em',
          color: 'var(--brand-text)',
        }}
      >
        CLENDAN
      </span>
    </div>
  )
}

function MobileMenu({ open, isSignedIn }: { open: boolean; isSignedIn: boolean | null | undefined }) {
  if (!open) return null
  return (
    <div
      className="md:hidden absolute top-full left-0 right-0 border-b border-brand-border"
      style={{ background: 'var(--brand-bg)' }}
    >
      <nav className="flex flex-col px-6 py-4 gap-1">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="py-2.5 text-sm font-mono text-brand-muted hover:text-brand-text transition-colors"
          >
            {link.label}
          </Link>
        ))}
        <div className="flex flex-col gap-2 mt-3 pt-3 border-t border-brand-border">
          {isSignedIn ? (
            <Link
              href="/dashboard"
              className="text-center rounded-sm px-5 py-2.5 text-sm font-mono font-medium transition-colors"
              style={{ background: '#00C853', color: '#000' }}
            >
              Dashboard →
            </Link>
          ) : (
            <>
              <Link
                href="/sign-in"
                className="text-center border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-5 py-2.5 text-sm font-mono transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/sign-up"
                className="text-center rounded-sm px-5 py-2.5 text-sm font-mono font-medium transition-colors"
                style={{ background: '#00C853', color: '#000' }}
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </nav>
    </div>
  )
}

export function Navbar() {
  const { isSignedIn } = useAuth()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 8)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  return (
    <header
      className="sticky top-0 z-50 transition-all duration-200"
      style={{
        background: scrolled ? 'var(--brand-surface)' : 'transparent',
        borderBottom: scrolled ? '1px solid var(--brand-border)' : '1px solid transparent',
        backdropFilter: scrolled ? 'blur(8px)' : 'none',
      }}
    >
      <div className="relative max-w-6xl mx-auto px-6 md:px-8 h-14 flex items-center justify-between">
        <Link href="/" aria-label="Clendan home">
          <LogoMark />
        </Link>

        <nav className="hidden md:flex items-center gap-7">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-mono text-brand-muted hover:text-brand-text transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-2">
          <ThemeToggle />
          {isSignedIn ? (
            <Link
              href="/dashboard"
              className="rounded-sm px-5 py-2.5 text-sm font-mono font-medium transition-colors"
              style={{ background: '#00C853', color: '#000' }}
            >
              Dashboard →
            </Link>
          ) : (
            <>
              <Link
                href="/sign-in"
                className="text-sm font-mono text-brand-muted hover:text-brand-text transition-colors px-3 py-2.5"
              >
                Sign in
              </Link>
              <Link
                href="/sign-up"
                className="rounded-sm px-5 py-2.5 text-sm font-mono font-medium transition-colors"
                style={{ background: '#00C853', color: '#000' }}
              >
                Get started
              </Link>
            </>
          )}
        </div>

        <button
          className="md:hidden text-brand-muted hover:text-brand-text transition-colors p-1"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label="Toggle menu"
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? '✕' : '☰'}
        </button>
      </div>

      <MobileMenu open={mobileOpen} isSignedIn={isSignedIn} />
    </header>
  )
}
