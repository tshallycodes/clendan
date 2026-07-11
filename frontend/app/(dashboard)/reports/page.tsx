import type { Metadata } from 'next'
import { ReportsClient } from '@/components/dashboard/reports/ReportsClient'

export const metadata: Metadata = { title: 'Reports' }

export default function ReportsPage() {
  return <ReportsClient />
}
