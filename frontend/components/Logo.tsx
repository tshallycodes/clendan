'use client'

import Link from 'next/link'
import { cn } from '@/lib/utils'

const SIZES = {
  xs: { icon: 16, text: 11 },
  sm: { icon: 20, text: 12 },
  md: { icon: 24, text: 14 },
  lg: { icon: 32, text: 18 },
}

interface LogoProps {
  size?: keyof typeof SIZES
  iconOnly?: boolean
  className?: string
  href?: string | null
}

function GearIcon({ px }: { px: number }) {
  return (
    <svg width={px} height={px} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path
        fill="#00C853"
        d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"
      />
    </svg>
  )
}

export function Logo({ size = 'md', iconOnly = false, className, href = '/' }: LogoProps) {
  const { icon, text } = SIZES[size]

  const inner = (
    <div className={cn('flex items-center gap-2 shrink-0', className)}>
      <GearIcon px={icon} />
      {!iconOnly && (
        <span
          style={{
            fontFamily: 'var(--font-heading)',
            fontWeight: 700,
            fontSize: text,
            letterSpacing: '0.01em',
            lineHeight: 1,
          }}
        >
          <span style={{ color: 'var(--brand-text)' }}>clendan</span>
          <span style={{ color: '#00C853' }}>.</span>
        </span>
      )}
    </div>
  )

  if (href === null) return inner
  return <Link href={href} aria-label="Clendan home">{inner}</Link>
}
