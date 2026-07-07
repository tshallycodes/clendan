import type { Metadata } from 'next'
import { PaymentRunsClient } from './PaymentRunsClient'

export const metadata: Metadata = { title: 'Payment Runs' }

export default function PaymentRunsPage() {
  return <PaymentRunsClient />
}
