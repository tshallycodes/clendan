import type { Metadata } from 'next'
import { TaxComplianceClient } from './TaxComplianceClient'

export const metadata: Metadata = { title: 'Tax Compliance' }

export default function TaxCompliancePage() {
  return <TaxComplianceClient />
}
