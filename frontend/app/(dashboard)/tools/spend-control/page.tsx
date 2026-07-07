import type { Metadata } from 'next'
import { SpendControlClient } from './SpendControlClient'

export const metadata: Metadata = { title: 'Spend Control' }

export default function SpendControlPage() {
  return <SpendControlClient />
}
