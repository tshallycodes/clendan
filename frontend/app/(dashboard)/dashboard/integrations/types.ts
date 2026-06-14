export type ConnectType = 'oauth' | 'plaid_link' | 'api_key' | 'codat_link'
export type IntegrationStatus = 'not_connected' | 'connecting' | 'syncing' | 'connected' | 'error' | 'disconnected'

export interface IntegrationDef {
  name: string
  slug: string
  category: string
  desc: string
  connectType: ConnectType
  comingSoon?: boolean
}

export interface XeroOrg {
  xero_tenant_id: string
  tenantName: string
}

export interface SyncEvent {
  id: string
  timestamp: string
  entity_type: string
  status: string
  records_synced: number
}
