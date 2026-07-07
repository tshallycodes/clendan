import type { Metadata } from 'next'
import { FinancialReportingClient } from './FinancialReportingClient'

export const metadata: Metadata = { title: 'Financial Reporting' }

export default function FinancialReportingPage() {
  return <FinancialReportingClient />
}
