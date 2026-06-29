'use client'

import { useTheme } from '@/components/Providers'
import { useEffect, useState } from 'react'
import { Sun, Moon } from '@phosphor-icons/react'

export function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])

  if (!mounted) return <div className="w-7 h-7" />

  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className={`w-7 h-7 flex items-center justify-center rounded-sm border border-brand-border text-brand-muted hover:text-brand-text hover:bg-brand-bg transition-colors ${className}`}
    >
      {isDark ? <Sun size={13} /> : <Moon size={13} />}
    </button>
  )
}
