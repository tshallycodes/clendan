'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { usePlaidLink, PlaidLinkOnSuccessMetadata } from 'react-plaid-link'
import { IntegrationDef, IntegrationStatus, XeroOrg } from './types'
import { IntegrationIconGrid } from './IntegrationIconGrid'
import { CredentialsDrawer } from './CredentialsDrawer'
import { XeroOrgModal } from './XeroOrgModal'
import { SyncLogDrawer } from './SyncLogDrawer'
import { IntegrationDetailDrawer } from './IntegrationDetailDrawer'
import { BankPicker } from './BankPicker'
import { BankDetailDrawer } from './BankDetailDrawer'
import { BankDef } from './banks-data'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const INTEGRATIONS: IntegrationDef[] = [
  // Accounting
  { name: 'QuickBooks', slug: 'quickbooks', category: 'Accounting', desc: 'Full AP/AR sync', connectType: 'oauth' },
  { name: 'Xero', slug: 'xero', category: 'Accounting', desc: 'Bills, invoices, payments', connectType: 'oauth' },
  { name: 'FreshBooks', slug: 'freshbooks', category: 'Accounting', desc: 'Invoice and payment sync', connectType: 'oauth' },
  // Payments
  { name: 'Stripe', slug: 'stripe', category: 'Payments', desc: 'Revenue and charges', connectType: 'oauth' },
  { name: 'GoCardless', slug: 'gocardless', category: 'Payments', desc: 'Direct debit', connectType: 'api_key' },
  { name: 'Adyen', slug: 'adyen', category: 'Payments', desc: 'Global payment processing', connectType: 'api_key' },
  { name: 'Wise', slug: 'wise', category: 'Payments', desc: 'International transfers', connectType: 'api_key' },
  { name: 'Square', slug: 'square', category: 'Payments', desc: 'Point of sale and invoicing', connectType: 'oauth' },
  // ERP
  { name: 'NetSuite', slug: 'netsuite', category: 'ERP', desc: 'Full ERP sync', connectType: 'api_key' },
  { name: 'SAP', slug: 'sap', category: 'ERP', desc: 'Enterprise ERP', connectType: 'api_key' },
  { name: 'Microsoft Dynamics 365', slug: 'dynamics365', category: 'ERP', desc: 'ERP and CRM', connectType: 'oauth' },
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
  'quickbooks', 'plaid', 'truelayer', 'mono', 'xero', 'stripe', 'gocardless', 'square',
  'codat', 'hubspot', 'gmail', 'outlook', 'google-drive',
  'freshbooks', 'adyen', 'wise',
  'netsuite', 'sap', 'dynamics365', 'salesforce', 'dropbox', 'onedrive',
]

const CATEGORIES = Array.from(new Set(INTEGRATIONS.map((i) => i.category)))

export function IntegrationsClient() {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [statuses, setStatuses] = useState<Record<string, IntegrationStatus>>({})
  const [lastSyncedAt, setLastSyncedAt] = useState<Record<string, string | null>>({})
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [connectedBankId, setConnectedBankId] = useState<string | null>(null)
  const [connectedBankName, setConnectedBankName] = useState<string | null>(null)
  const [connectedTruelayerName, setConnectedTruelayerName] = useState<string | null>(null)
  const [connectedMonoName, setConnectedMonoName] = useState<string | null>(null)
  const [plaidToken, setPlaidToken] = useState<string | null>(null)

  // Drawers / modals
  const [showCredentialsDrawer, setShowCredentialsDrawer] = useState(false)
  const [activeCredentialSlug, setActiveCredentialSlug] = useState<string | null>(null)
  const [showXeroModal, setShowXeroModal] = useState(false)
  const [xeroOrgs, setXeroOrgs] = useState<XeroOrg[]>([])
  const [pendingXeroIntegrationId, setPendingXeroIntegrationId] = useState<string | null>(null)
  const [showSyncLog, setShowSyncLog] = useState<{ slug: string; name: string } | null>(null)
  const [detailSlug, setDetailSlug] = useState<string | null>(null)
  const [bankDetailBank, setBankDetailBank] = useState<BankDef | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { open: openPlaidLink, ready: plaidReady } = usePlaidLink({
    token: plaidToken,
    onSuccess: useCallback(async (public_token: string, metadata: PlaidLinkOnSuccessMetadata) => {
      const institution_id = metadata.institution?.institution_id ?? null
      const institution_name = metadata.institution?.name ?? null
      setStatus('plaid', 'syncing')
      setPlaidToken(null)
      setConnecting(null)
      try {
        const authToken = await getToken()
        await fetch(`${API}/v1/integrations/plaid/exchange-token`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ public_token, institution_id, institution_name }),
        })
        if (institution_id) setConnectedBankId(institution_id)
        if (institution_name) setConnectedBankName(institution_name)
        toast('Bank connected — syncing transactions', 'success')
      } catch (err) {
        setStatus('plaid', 'error')
        setConnecting(null)
        toast(err instanceof Error ? err.message : 'Bank connection failed', 'error')
      }
    }, [getToken]), // eslint-disable-line react-hooks/exhaustive-deps
    onExit: useCallback(() => {
      setPlaidToken(null)
      setConnecting(null)
    }, []),
  })

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
        if (!res.ok) return { slug, status: 'not_connected' as IntegrationStatus, last_synced_at: null, institution_id: null }
        const json = await res.json()
        const raw: string = json.data?.status ?? json.status ?? 'not_connected'
        const synced: string | null = json.data?.last_synced_at ?? null
        const institutionId: string | null = slug === 'plaid' ? (json.data?.institution_id ?? null) : null
        const institutionName: string | null = (slug === 'plaid' || slug === 'truelayer' || slug === 'mono') ? (json.data?.institution_name ?? null) : null
        return { slug, status: raw as IntegrationStatus, last_synced_at: synced, institution_id: institutionId, institution_name: institutionName }
      }),
    )
    const nextStatuses: Record<string, IntegrationStatus> = {}
    const nextSynced: Record<string, string | null> = {}
    for (const r of results) {
      if (r.status === 'fulfilled') {
        nextStatuses[r.value.slug] = r.value.status
        nextSynced[r.value.slug] = r.value.last_synced_at
        if (r.value.slug === 'plaid' && r.value.institution_id) {
          setConnectedBankId(r.value.institution_id)
          setConnectedBankName(r.value.institution_name)
        }
        if (r.value.slug === 'truelayer' && r.value.institution_name) {
          setConnectedTruelayerName(r.value.institution_name)
        }
        if (r.value.slug === 'mono' && r.value.institution_name) {
          setConnectedMonoName(r.value.institution_name)
        }
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
        const xeroSelect = params.get('xero_select')

        if (connected) {
          setStatus(connected, 'syncing')
          toast(`${connected} connected — syncing data`, 'success')
        }
        if (oauthError) {
          toast(`Connection failed: ${oauthError.replace(/_/g, ' ')}`, 'error')
        }
        if (xeroSelect) {
          try {
            const authToken = await getToken()
            const res = await fetch(`${API}/v1/integrations/xero/pending-orgs/${xeroSelect}`, {
              headers: { Authorization: `Bearer ${authToken}` },
            })
            if (res.ok) {
              const json = await res.json()
              const orgs: XeroOrg[] = json.data?.orgs ?? []
              if (orgs.length > 0) {
                setXeroOrgs(orgs)
                setPendingXeroIntegrationId(xeroSelect)
                setShowXeroModal(true)
              }
            }
          } catch {
            toast('Xero org selection failed — please try connecting again', 'error')
          }
        }

        if (connected || oauthError || xeroSelect) {
          params.delete('connected')
          params.delete('error')
          params.delete('xero_select')
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

  async function handleConnectBank(bank: BankDef) {
    if (connecting) return

    if (bank.provider === 'truelayer') {
      setBankDetailBank(null)
      setConnecting('truelayer')
      try {
        const authToken = await getToken()
        const res = await fetch(`${API}/v1/integrations/truelayer/connect`, {
          headers: { Authorization: `Bearer ${authToken}` },
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail ?? body.error ?? `Server error ${res.status}`)
        }
        const json = await res.json()
        const url: string = json.data?.auth_url ?? json.auth_url
        if (!url) throw new Error('No auth URL returned from TrueLayer')
        window.location.href = url
      } catch (err) {
        setStatus('truelayer', 'error')
        setConnecting(null)
        toast(err instanceof Error ? err.message : 'TrueLayer connection failed', 'error')
      }
      return
    }

    if (bank.provider === 'mono') {
      setBankDetailBank(null)
      setConnecting('mono')
      try {
        const authToken = await getToken()
        const res = await fetch(`${API}/v1/integrations/mono/connect`, {
          headers: { Authorization: `Bearer ${authToken}` },
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail ?? body.error ?? `Server error ${res.status}`)
        }
        const json = await res.json()
        const url: string = json.data?.auth_url ?? json.auth_url
        if (!url) throw new Error('No connect URL returned from Mono')
        window.location.href = url
      } catch (err) {
        setStatus('mono', 'error')
        setConnecting(null)
        toast(err instanceof Error ? err.message : 'Mono connection failed', 'error')
      }
      return
    }

    setBankDetailBank(null)
    setConnecting('plaid')
    try {
      const authToken = await getToken()
      const res = await fetch(`${API}/v1/integrations/plaid/link-token`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ institution_id: bank.institution_id ?? null }),
      })
      if (!res.ok) throw new Error('Failed to create Plaid link token')
      const json = await res.json()
      const token: string | undefined = json.data?.link_token ?? json.link_token
      if (!token) throw new Error('Plaid returned empty link token')
      setPlaidToken(token)
    } catch (err) {
      setStatus('plaid', 'error')
      setConnecting(null)
      toast(err instanceof Error ? err.message : 'Bank connection failed', 'error')
    }
  }

  async function handleDisconnectDirect(slug: string) {
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
      toast(err instanceof Error ? err.message : 'Disconnect failed', 'error')
    }
  }

  async function handleDisconnectConnection(provider: string, integrationId: string) {
    try {
      const token = await getToken()
      const res = await fetch(`${API}/v1/integrations/${provider}/connections/${integrationId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const json = await res.json().catch(() => ({}))
        throw new Error(json.detail ?? json.error ?? 'Disconnect failed')
      }
      await fetchAllStatuses()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Disconnect failed', 'error')
    }
  }

  async function handleResyncConnection(provider: string, integrationId: string) {
    try {
      const token = await getToken()
      await fetch(`${API}/v1/integrations/${provider}/connections/${integrationId}/sync`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      setStatus(provider, 'syncing')
    } catch { /* silent — status poll will correct */ }
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
    toast(`${slug} connected — syncing data`, 'success')
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
    toast('Xero connected — syncing data', 'success')
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

  const syncLogName = showSyncLog?.name ?? ''

  const detailIntg = detailSlug
    ? (INTEGRATIONS.find((i) => i.slug === detailSlug) ?? null)
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
      {!loading && (
        <>
          {/* Banking — always first, uses BankPicker */}
          <section className="space-y-3">
            <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
              Banking
            </h2>
            <BankPicker
              plaidStatus={statuses['plaid'] ?? 'not_connected'}
              connectedInstitutionId={connectedBankId}
              connectedBankName={connectedBankName}
              truelayerStatus={statuses['truelayer'] ?? 'not_connected'}
              connectedTruelayerName={connectedTruelayerName}
              monoStatus={statuses['mono'] ?? 'not_connected'}
              connectedMonoName={connectedMonoName}
              connecting={connecting === 'plaid' || connecting === 'truelayer' || connecting === 'mono'}
              onViewDetail={setBankDetailBank}
              onConnect={(region) => {
                if (region === 'eu') {
                  handleConnectBank({ id: 'truelayer', name: 'Bank', abbr: 'EU', color: '#1a1a1a', domain: '', provider: 'truelayer', region: 'eu' })
                } else if (region === 'africa') {
                  handleConnectBank({ id: 'mono', name: 'Bank', abbr: 'AF', color: '#1a1a1a', domain: '', provider: 'mono', region: 'africa' })
                } else {
                  handleConnectBank({ id: 'other', name: 'Other Bank', abbr: '+', color: '#1a1a1a', domain: '', provider: 'plaid', region: 'us' })
                }
              }}
            />
          </section>

          {/* All other categories */}
          {CATEGORIES.map((cat) => {
            const items = INTEGRATIONS.filter((i) => i.category === cat)
            return (
              <section key={cat} className="space-y-3">
                <h2 className="text-[10px] font-mono uppercase tracking-widest text-brand-muted border-b border-brand-border pb-2">
                  {cat}
                </h2>
                <IntegrationIconGrid
                  integrations={items}
                  statuses={statuses}
                  onViewDetail={(intg) => setDetailSlug(intg.slug)}
                />
              </section>
            )
          })}
        </>
      )}

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

      {/* Bank detail drawer */}
      <BankDetailDrawer
        bank={bankDetailBank}
        onClose={() => setBankDetailBank(null)}
        onConnect={handleConnectBank}
        onDisconnect={async (integrationId, provider) => {
          await handleDisconnectConnection(provider, integrationId)
        }}
        onResync={async (integrationId, provider) => {
          await handleResyncConnection(provider, integrationId)
        }}
        onSyncLog={(slug, name) => {
          setShowSyncLog({ slug, name })
          setBankDetailBank(null)
        }}
      />

      {/* Sync log drawer */}
      <SyncLogDrawer
        slug={showSyncLog?.slug ?? null}
        integrationName={syncLogName}
        onClose={() => setShowSyncLog(null)}
      />

      {/* Integration detail drawer */}
      <IntegrationDetailDrawer
        slug={detailSlug}
        intg={detailIntg}
        status={detailSlug ? (statuses[detailSlug] ?? 'not_connected') : 'not_connected'}
        lastSyncedAt={detailSlug ? (lastSyncedAt[detailSlug] ?? null) : null}
        onClose={() => setDetailSlug(null)}
        onConnect={() => {
          if (detailIntg) { setDetailSlug(null); handleConnect(detailIntg) }
        }}
        onDisconnect={async () => {
          if (detailSlug) { await handleDisconnectDirect(detailSlug); setDetailSlug(null) }
        }}
        onResync={async () => {
          if (detailSlug) await handleResync(detailSlug)
        }}
        onSyncLog={() => {
          if (detailSlug) {
            setShowSyncLog({ slug: detailSlug, name: detailIntg?.name ?? detailSlug })
            setDetailSlug(null)
          }
        }}
      />

    </div>
  )
}
