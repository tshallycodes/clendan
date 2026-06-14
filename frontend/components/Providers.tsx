'use client'

import { createContext, useContext, useEffect, useState } from 'react'

interface ThemeCtx {
  theme: string
  setTheme: (t: string) => void
}

const ThemeContext = createContext<ThemeCtx>({ theme: 'dark', setTheme: () => {} })

export function useTheme() {
  return useContext(ThemeContext)
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState('dark')

  useEffect(() => {
    const saved = localStorage.getItem('theme') ?? 'dark'
    setThemeState(saved)
  }, [])

  function setTheme(t: string) {
    setThemeState(t)
    localStorage.setItem('theme', t)
    document.documentElement.classList.toggle('dark', t === 'dark')
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
