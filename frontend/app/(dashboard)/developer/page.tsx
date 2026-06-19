import type { Metadata } from 'next'
import { DeveloperPageClient } from '@/components/dashboard/developer/DeveloperPageClient'

export const metadata: Metadata = { title: 'Developer' }

export default function DeveloperPage() {
  return <DeveloperPageClient />
}
