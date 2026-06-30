import type { Metadata } from 'next'
import { Sora, Noto_Sans_Display } from 'next/font/google'
import { ClerkProvider } from '@clerk/nextjs'
import { Providers } from '@/components/Providers'
import { WarningBanner } from '@/components/WarningBanner'
import './globals.css'

const sora = Sora({
  variable: '--font-heading',
  subsets: ['latin'],
  weight: ['300', '400', '500', '600'],
})

const notoSansDisplay = Noto_Sans_Display({
  variable: '--font-body',
  subsets: ['latin'],
  weight: ['300', '400', '500', '600'],
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
      <html lang="en" className={`${sora.variable} ${notoSansDisplay.variable} h-full`} suppressHydrationWarning>
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
