import type { Metadata } from 'next'
import { Syne, IBM_Plex_Mono } from 'next/font/google'
import { ClerkProvider } from '@clerk/nextjs'
import { Providers } from '@/components/Providers'
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
  description: 'Autonomous AI tools for financial operations',
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${syne.variable} ${ibmPlexMono.variable} h-full`} suppressHydrationWarning>
        <body className="min-h-full bg-brand-bg text-brand-text">
          <div className="w-full bg-[#f5a623] text-black text-[11px] font-mono font-medium text-center py-1.5 px-4 tracking-wide z-[9999] relative">
            This platform is under active development — not intended for public use.
          </div>
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  )
}
