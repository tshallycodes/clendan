import type { Metadata } from 'next'
import { TeamPageClient } from '@/components/dashboard/settings/team/TeamPageClient'

export const metadata: Metadata = { title: 'Team' }

export default function TeamSettingsPage() {
  return <TeamPageClient />
}
