import type { Metadata } from 'next'
import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { ClientsClient } from './ClientsClient'
import type { FirmClient } from '@/components/dashboard/ClientSwitcher'

export const metadata: Metadata = { title: 'Clients' }

interface ClientsData {
  clients: FirmClient[]
}

export default async function ClientsPage() {
  let clients: FirmClient[] = []
  try {
    const token = await getBackendToken()
    if (token) {
      const data = await apiGet<ClientsData>('/firms/clients', token)
      clients = data.clients ?? []
    }
  } catch {
    /* backend not running or user not in a firm — render empty portfolio */
  }

  return <ClientsClient initialClients={clients} />
}
