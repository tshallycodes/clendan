import type { Metadata } from 'next'
import { Syne, IBM_Plex_Mono } from 'next/font/google'
import { ClerkProvider } from '@clerk/nextjs'
import { Providers } from '@/components/Providers'
import { WarningBanner } from '@/components/WarningBanner'
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
  title: {
    template: 'Clendan - %s',
    default: 'Clendan — AI Financial Agent OS',
  },
  description: 'Autonomous AI tools for financial operations',
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${syne.variable} ${ibmPlexMono.variable} h-full`} suppressHydrationWarning>
        <head>
          <script
            dangerouslySetInnerHTML={{
              __html: `try{var t=localStorage.getItem('theme')||'dark';document.documentElement.classList.toggle('dark',t==='dark')}catch(e){}`,
            }}
          />
        </head>
        <body className="min-h-full bg-brand-bg text-brand-text">
          <WarningBanner />
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  )
}
