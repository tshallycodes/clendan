'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { usePlaidLink } from 'react-plaid-link'
import { IntegrationDef, IntegrationStatus, XeroOrg } from './types'
import { IntegrationCard } from './IntegrationCard'
import { CredentialsDrawer } from './CredentialsDrawer'
import { XeroOrgModal } from './XeroOrgModal'
import { SyncLogDrawer } from './SyncLogDrawer'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

const INTEGRATIONS: IntegrationDef[] = [
  // Accounting
  { name: 'QuickBooks', slug: 'quickbooks', category: 'Accounting', desc: 'Full AP/AR sync', connectType: 'oauth' },
  { name: 'Xero', slug: 'xero', category: 'Accounting', desc: 'Bills, invoices, payments', connectType: 'oauth' },
  { name: 'FreshBooks', slug: 'freshbooks', category: 'Accounting', desc: 'Invoice and payment sync', connectType: 'oauth' },
  { name: 'Sage', slug: 'sage', category: 'Accounting', desc: 'Accounting and payroll', connectType: 'oauth' },
  { name: 'Wave', slug: 'wave', category: 'Accounting', desc: 'Free accounting for SMBs', connectType: 'oauth' },
  // Banking
  { name: 'Plaid', slug: 'plaid', category: 'Banking', desc: 'Bank feeds and transactions', connectType: 'plaid_link' },
  { name: 'TrueLayer', slug: 'truelayer', category: 'Banking', desc: 'Open banking (UK/EU)', connectType: 'oauth' },
  { name: 'Codat', slug: 'codat', category: 'Banking', desc: '50+ accounting platforms via one connection', connectType: 'codat_link' },
  { name: 'Nordigen', slug: 'nordigen', category: 'Banking', desc: 'EU bank data', connectType: 'api_key' },
  // Payments
  { name: 'Stripe', slug: 'stripe', category: 'Payments', desc: 'Revenue and charges', connectType: 'oauth' },
  { name: 'GoCardless', slug: 'gocardless', category: 'Payments', desc: 'Direct debit', connectType: 'api_key' },
  { name: 'Adyen', slug: 'adyen', category: 'Payments', desc: 'Global payment processing', connectType: 'api_key' },
  { name: 'Wise', slug: 'wise', category: 'Payments', desc: 'International transfers', connectType: 'oauth' },
  // ERP
  { name: 'NetSuite', slug: 'netsuite', category: 'ERP', desc: 'Full ERP sync', connectType: 'api_key' },
  { name: 'SAP', slug: 'sap', category: 'ERP', desc: 'Enterprise ERP', connectType: 'api_key' },
  { name: 'Microsoft Dynamics 365', slug: 'dynamics365', category: 'ERP', desc: 'ERP and CRM', connectType: 'oauth' },
  { name: 'Sage Intacct', slug: 'sage-intacct', category: 'ERP', desc: 'Cloud ERP', connectType: 'api_key' },
  // CRM
  { name: 'Salesforce', slug: 'salesforce', category: 'CRM', desc: 'Customer and pipeline data', connectType: 'oauth' },
  { name: 'HubSpot', slug: 'hubspot', category: 'CRM', desc: 'CRM and deal sync', connectType: 'oauth' },
  // Document & Email
  { name: 'Gmail', slug: 'gmail', category: 'Document & Email', desc: 'Invoice ingestion from email', connectType: 'oauth' },
  { name: 'Outlook', slug: 'outlook', category: 'Document & Email', desc: 'Invoice ingestion from email', connectType: 'oauth' },
  { name: 'Google Drive', slug: 'google-drive', category: 'Document & Email', desc: 'Document storage and ingestion', connectType: 'oauth' },
  { name: 'Dropbox', slug: 'dropbox', category: 'Document & Email', desc: 'Document storage', connectType: 'oauth' },
  { name: 'OneDrive', slug: 'onedrive', category: 'Document & Email', desc: 'Document storage', connectType: 'oauth' },
]

const STATUSABLE_SLUGS = [
  'quickbooks', 'plaid', 'xero', 'stripe', 'gocardless',
  'truelayer', 'codat', 'hubspot', 'gmail', 'outlook', 'google-drive',
  'freshbooks', 'sage', 'wave', 'nordigen', 'adyen', 'wise',
  'netsuite', 'sap', 'dynamics365', 'sage-intacct', 'salesforce', 'dropbox', 'onedrive',
]

const CATEGORIES = Array.from(new Set(INTEGRATIONS.map((i) => i.category)))

export function IntegrationsClient() {
  const { getToken } = useAuth()
  const [statuses, setStatuses] = useState<Record<string, IntegrationStatus>>({})
  const [lastSyncedAt, setLastSyncedAt] = useState<Record<string, string | null>>({})
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [plaidToken, setPlaidToken] = useState<string | null>(null)

  // Drawers / modals
  const [showCredentialsDrawer, setShowCredentialsDrawer] = useState(false)
  const [activeCredentialSlug, setActiveCredentialSlug] = useState<string | null>(null)
  const [showXeroModal, setShowXeroModal] = useState(false)
  const [xeroOrgs, setXeroOrgs] = useState<XeroOrg[]>([])
  const [pendingXeroIntegrationId, setPendingXeroIntegrationId] = useState<string | null>(null)
  const [showSyncLog, setShowSyncLog] = useState<string | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { open: openPlaidLink, ready: plaidReady } = usePlaidLink({
    token: plaidToken ?? '',
    onSuccess: useCallback(async (public_token: string) => {
      setStatus('plaid', 'syncing')
      setPlaidToken(null)
      try {
        const authToken = await getToken()
        await fetch(`${API}/v1/integrations/plaid/exchange-token`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ public_token }),
        })
        showToast('Plaid connected â€” syncing bank data')
      } catch {
        setStatus('plaid', 'error')
      }
    }, [getToken]), // eslint-disable-line react-hooks/exhaustive-deps
    onExit: useCallback(() => {
      setPlaidToken(null)
      setConnecting(null)
    }, []),
  })

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  function setStatus(slug: string, status: IntegrationStatus) {
    setStatuses((prev) => ({ ...prev, [slug]: status }))
  }

  async function fetchAllStatuses() {
    const token = await getToken()
    const results = await Promise.allSettled(
      STATUSABLE_SLUGS.map(async (slug) => {
        const res = await fetch(`${API}/v1/integrations/${slug}/status`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) return { slug, status: 'not_connected' as IntegrationStatus, last_synced_at: null }
        const json = await res.json()
        const raw: string = json.data?.status ?? json.status ?? 'not_connected'
        const synced: string | null = json.data?.last_synced_at ?? null
        return { slug, status: raw as IntegrationStatus, last_synced_at: synced }
      }),
    )
    const nextStatuses: Record<string, IntegrationStatus> = {}
    const nextSynced: Record<string, string | null> = {}
    for (const r of results) {
      if (r.status === 'fulfilled') {
        nextStatuses[r.value.slug] = r.value.status
        nextSynced[r.value.slug] = r.value.last_synced_at
      }
    }
    setStatuses(nextStatuses)
    setLastSyncedAt(nextSynced)
  }

  // Initial load + URL param handling
  useEffect(() => {
    async function init() {
      setLoading(true)
      try {
        await fetchAllStatuses()
      } catch {
        // statuses will default to not_connected
      }
      setLoading(false)

      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search)
        const connected = params.get('connected')
        const oauthError = params.get('error')
        if (connected) {
          setStatus(connected, 'syncing')
          showToast(`${connected} connected — syncing data`)
        }
        if (oauthError) {
          showToast(`Connection failed: ${oauthError.replace(/_/g, ' ')}`)
        }
        if (connected || oauthError) {
          params.delete('connected')
          params.delete('error')
          const newSearch = params.toString()
          window.history.replaceState(null, '', newSearch ? `?${newSearch}` : window.location.pathname)
        }
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Open Plaid Link once token is fetched and widget is ready
  useEffect(() => {
    if (plaidToken && plaidReady) {
      openPlaidLink()
    }
  }, [plaidToken, plaidReady, openPlaidLink])

  // Polling when any integration is connecting or syncing
  useEffect(() => {
    const needsPoll = Object.values(statuses).some(
      (s) => s === 'connecting' || s === 'syncing',
    )
    if (needsPoll && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        await fetchAllStatuses()
      }, 3000)
    } else if (!needsPoll && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statuses])

  async function handleConnect(intg: IntegrationDef) {
    if (connecting) return

    if (intg.connectType === 'api_key') {
      setActiveCredentialSlug(intg.slug)
      setShowCredentialsDrawer(true)
      return
    }

    if (intg.connectType === 'plaid_link') {
      setConnecting('plaid')
      try {
        const authToken = await getToken()
        const res = await fetch(`${API}/v1/integrations/plaid/link-token`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${authToken}` },
        })
        if (!res.ok) throw new Error('Failed to create Plaid link token')
        const json = await res.json()
        const token: string = json.data?.link_token ?? json.link_token
        setPlaidToken(token)
      } catch {
        setStatus('plaid', 'error')
        setConnecting(null)
      }
      return
    }

    if (intg.connectType === 'codat_link') {
      setConnecting(intg.slug)
      try {
        const token = await getToken()
        const res = await fetch(`${API}/v1/integrations/codat/connect`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) throw new Error('Failed to get Codat link')
        const json = await res.json()
        const url: string = json.data?.link_url ?? json.link_url
        window.open(url, '_blank', 'noopener,noreferrer')
        setStatus(intg.slug, 'connecting')
      } catch {
        setStatus(intg.slug, 'error')
      } finally {
        setConnecting(null)
      }
      return
    }

    // oauth
    setConnecting(intg.slug)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/integrations/${intg.slug}/connect`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Failed to get auth URL')
      const json = await res.json()
      const url: string = json.data?.auth_url ?? json.auth_url

      if (intg.slug === 'xero') {
        // Xero may return orgs list for multi-org
        const orgs: XeroOrg[] = json.data?.orgs ?? json.orgs ?? []
        const integrationId: string = json.data?.integration_id ?? json.integration_id ?? ''
        if (orgs.length > 1) {
          setXeroOrgs(orgs)
          setPendingXeroIntegrationId(integrationId)
          setShowXeroModal(true)
          setConnecting(null)
          return
        }
      }

      setStatus(intg.slug, 'connecting')
      window.location.href = url
    } catch {
      setStatus(intg.slug, 'error')
      setConnecting(null)
    }
  }

  async function handleCredentialsSubmit(slug: string, credentials: Record<string, string>) {
    const token = await getToken()
    const res = await fetch(`${API}/v1/integrations/${slug}/connect`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    })
    if (!res.ok) {
      const json = await res.json().catch(() => ({}))
      throw new Error(json.detail ?? json.error ?? 'Connection failed')
    }
    setShowCredentialsDrawer(false)
    setActiveCredentialSlug(null)
    setStatus(slug, 'syncing')
    showToast(`${slug} connected â€” syncing data`)
  }

  async function handleXeroOrgConfirm(xeroTenantId: string) {
    if (!pendingXeroIntegrationId) return
    const token = await getToken()
    const res = await fetch(`${API}/v1/integrations/xero/select-tenant`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ integration_id: pendingXeroIntegrationId, xero_tenant_id: xeroTenantId }),
    })
    if (!res.ok) {
      const json = await res.json().catch(() => ({}))
      throw new Error(json.error ?? 'Failed to select organisation')
    }
    setShowXeroModal(false)
    setXeroOrgs([])
    setPendingXeroIntegrationId(null)
    setStatus('xero', 'syncing')
    showToast('Xero connected â€” syncing data')
  }

  async function handleDisconnect(slug: string) {
    if (confirming !== slug) {
      setConfirming(slug)
      return
    }
    setConfirming(null)
    setDisconnecting(slug)
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/integrations/${slug}/disconnect`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        throw new Error(json.detail ?? json.error ?? 'Disconnect failed')
      }
      setStatus(slug, 'disconnected')
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Disconnect failed')
    } finally {
      setDisconnecting(null)
    }
  }

  async function handleResync(slug: string) {
    setStatus(slug, 'syncing')
    try {
      const token = await getToken()
      await fetch(`${API}/v1/integrations/${slug}/sync`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch {
      // silent fail — status poll will correct
    }
  }

  function getStatusForSlug(slug: string): IntegrationStatus {
    return statuses[slug] ?? 'not_connected'
  }

  const syncLogIntg = showSyncLog
    ? (INTEGRATIONS.find((i) => i.slug === showSyncLog) ?? null)
    : null

  return (
    <div className="p-6 space-y-8 relative">
      {/* Page header */}
      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">Integrations</h1>
        <p className="text-[10px] font-mono text-brand-muted mt-1 uppercase tracking-widest">
          Connect your financial systems
        </p>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-24 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />
          ))}
        </div>
      )}

      {/* Integration sections by category */}
      {!loading && CATEGORIES.map((cat) => {
        const items = INTEGRATIONS.filter((i) => i.category === cat)
        return (
          <section key={cat} className="space-y-3">
            <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
              {cat}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((intg) => {
                const status = getStatusForSlug(intg.slug)
                return (
                  <IntegrationCard
                    key={intg.slug}
                    intg={intg}
                    status={status}
                    lastSyncedAt={lastSyncedAt[intg.slug] ?? null}
                    onConnect={() => handleConnect(intg)}
                    onDisconnect={() => handleDisconnect(intg.slug)}
                    onResync={() => handleResync(intg.slug)}
                    onViewLog={() => setShowSyncLog(intg.slug)}
                    confirming={confirming === intg.slug}
                    onCancelConfirm={() => setConfirming(null)}
                    connecting={connecting === intg.slug}
                    disconnecting={disconnecting === intg.slug}
                  />
                )
              })}
            </div>
          </section>
        )
      })}

      {/* API key / credentials drawer */}
      <CredentialsDrawer
        slug={activeCredentialSlug}
        open={showCredentialsDrawer}
        onClose={() => { setShowCredentialsDrawer(false); setActiveCredentialSlug(null) }}
        onSubmit={handleCredentialsSubmit}
      />

      {/* Xero org selector */}
      <XeroOrgModal
        open={showXeroModal}
        orgs={xeroOrgs}
        onConfirm={handleXeroOrgConfirm}
        onClose={() => {
          setShowXeroModal(false)
          setPendingXeroIntegrationId(null)
          setXeroOrgs([])
        }}
      />

      {/* Sync log drawer */}
      <SyncLogDrawer
        slug={showSyncLog}
        integrationName={syncLogIntg?.name ?? ''}
        onClose={() => setShowSyncLog(null)}
      />

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-brand-surface border border-brand-border rounded-sm px-4 py-3 z-50 shadow-none">
          <p className="text-xs font-mono text-brand-text">{toast}</p>
        </div>
      )}
    </div>
  )
}
