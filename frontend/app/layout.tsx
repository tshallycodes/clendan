import type { Metadata } from 'next'
import { Syne, IBM_Plex_Mono } from 'next/font/google'
import { ClerkProvider } from '@clerk/nextjs'
import './globals.css'

const syne = Syne({
  variable: '--font-syne',
  subsets: ['latin'],
  weight: ['400', '600', '700', '800'],
})

const ibmPlexMono = IBM_Plex_Mono({
  variable: '--font-ibm-plex-mono',
  subsets: ['latin'],
  weight: ['400', '500'],
})

export const metadata: Metadata = {
  title: 'Clendan — AI Financial Agent OS',
  description: 'Autonomous AI workers for financial operations',
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${syne.variable} ${ibmPlexMono.variable} h-full`}>
        <body className="min-h-full bg-brand-bg text-brand-text">{children}</body>
      </html>
    </ClerkProvider>
  )
}
