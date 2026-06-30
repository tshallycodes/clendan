'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { useAuth } from '@clerk/nextjs'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Logo } from '@/components/Logo'

const NAV_LINKS = [
  { label: 'How It Works', href: '/how-it-works' },
  { label: 'Tools', href: '/tools' },
  { label: 'API Tools', href: '/api-tools' },
  { label: 'Pricing', href: '/pricing' },
]

function MobileMenu({ open, isSignedIn }: { open: boolean; isSignedIn: boolean | null | undefined }) {
  if (!open) return null
  return (
    <div className="md:hidden border-t border-brand-border">
      <nav className="flex flex-col px-6 py-4 gap-1">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="py-2.5 text-sm font-body text-brand-muted hover:text-brand-text transition-colors"
          >
            {link.label}
          </Link>
        ))}
        <div className="flex flex-col gap-2 mt-3 pt-3 border-t border-brand-border">
          {isSignedIn ? (
            <Link
              href="/dashboard"
              className="text-center rounded-sm px-5 py-2.5 text-sm font-body font-medium transition-colors"
              style={{ background: '#00C853', color: '#000' }}
            >
              Dashboard →
            </Link>
          ) : (
            <>
              <Link
                href="/sign-in"
                className="text-center border border-brand-border text-brand-text hover:bg-brand-elevated rounded-sm px-5 py-2.5 text-sm font-body transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/sign-up"
                className="text-center rounded-sm px-5 py-2.5 text-sm font-body font-medium transition-colors"
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
    <div className="fixed top-4 left-0 right-0 z-50 flex justify-center pointer-events-none">
      <motion.header
        initial={{ y: -60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 400, damping: 12, mass: 0.8 }}
        className="pointer-events-auto w-[95%] overflow-hidden"
        style={{
          background: 'var(--brand-surface)',
          border: '1px solid var(--brand-border)',
          borderRadius: '10px',
          backdropFilter: 'blur(12px)',
          boxShadow: scrolled ? 'var(--nav-shadow-raised)' : 'var(--nav-shadow)',
          transition: 'box-shadow 0.2s ease',
        }}
      >
        <div className="relative px-6 md:px-8 h-14 flex items-center justify-between">
          <Logo size="lg" />

          <nav className="hidden md:flex items-center gap-7">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm font-body text-brand-muted hover:text-brand-text transition-colors"
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
                className="rounded-sm px-5 py-2.5 text-sm font-body font-medium transition-colors"
                style={{ background: '#00C853', color: '#000' }}
              >
                Dashboard →
              </Link>
            ) : (
              <>
                <Link
                  href="/sign-in"
                  className="text-sm font-body text-brand-muted hover:text-brand-text transition-colors px-3 py-2.5"
                >
                  Sign in
                </Link>
                <Link
                  href="/sign-up"
                  className="rounded-sm px-5 py-2.5 text-sm font-body font-medium transition-colors"
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
      </motion.header>
    </div>
  )
}
