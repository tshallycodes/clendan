import { Navbar } from '@/components/marketing/Navbar'
import { Footer } from '@/components/marketing/Footer'
import { ClenButton } from '@/components/clen/ClenButton'

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col min-h-screen bg-brand-bg">
      <Navbar />
      <main className="flex-1 pt-[88px]">{children}</main>
      <Footer />
      <ClenButton />
    </div>
  )
}
