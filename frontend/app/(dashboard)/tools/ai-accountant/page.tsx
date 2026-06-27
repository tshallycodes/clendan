import type { Metadata } from 'next'
import { AiAccountantClient } from './AiAccountantClient'

export const metadata: Metadata = { title: 'AI Accountant' }

export default function AiAccountantPage() {
  return <AiAccountantClient />
}
