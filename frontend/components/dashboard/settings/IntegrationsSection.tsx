'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useToast } from '@/components/Providers'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const INTEGRATION_META: Record<string, { name: string; desc: string }> = {
  quickbooks:   { name: 'QuickBooks',            desc: 'Accounting sync, invoices, and company data' },
  xero:         { name: 'Xero',                  desc: 'Bills, invoices, payments' },
  freshbooks:   { name: 'FreshBooks',            desc: 'Invoice and payment sync' },
  stripe:       { name: 'Stripe',                desc: 'Revenue and charges' },
  gocardless:   { name: 'GoCardless',            desc: 'Direct debit' },
  adyen:        { name: 'Adyen',                 desc: 'Global payment processing' },
  wise:         { name: 'Wise',                  desc: 'International transfers' },
  square:       { name: 'Square',               desc: 'Point of sale and invoicing' },
  netsuite:     { name: 'NetSuite',              desc: 'Full ERP sync' },
  sap:          { name: 'SAP',                   desc: 'Enterprise ERP' },
  dynamics365:  { name: 'Microsoft Dynamics 365', desc: 'ERP and CRM' },
  salesforce:   { name: 'Salesforce',            desc: 'Customer and pipeline data' },
  hubspot:      { name: 'HubSpot',               desc: 'CRM and deal sync' },
  gmail:        { name: 'Gmail',                 desc: 'Invoice ingestion from email' },
  outlook:      { name: 'Outlook',               desc: 'Invoice ingestion from email' },
  'google-drive': { name: 'Google Drive',        desc: 'Document storage and ingestion' },
  dropbox:      { name: 'Dropbox',               desc: 'Document storage' },
  onedrive:     { name: 'OneDrive',              desc: 'Document storage' },
  plaid:        { name: 'Plaid',                 desc: 'Bank account connections and transaction sync' },
  truelayer:    { name: 'TrueLayer',             desc: 'Open banking connections (EU)' },
}

const STATUSABLE_SLUGS = [
  'quickbooks', 'plaid', 'truelayer', 'xero', 'stripe', 'gocardless', 'square',
  'hubspot', 'gmail', 'outlook', 'google-drive',
  'freshbooks', 'adyen', 'wise',
  'netsuite', 'sap', 'dynamics365', 'salesforce', 'dropbox', 'onedrive',
]

interface IntegrationState {
  slug: string
  status: 'connected' | 'syncing' | 'not_connected' | 'error' | 'disconnected'
  connected_at: string | null
  last_synced_at: string | null
  institution_name: string | null
}

export function IntegrationsSection() {
  const { getToken } = useAuth()
  const { toast } = useToast()
  const [integrations, setIntegrations] = useState<IntegrationState[]>([])
  const [loading, setLoading] = useState(true)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [confirmSlug, setConfirmSlug] = useState<string | null>(null)
  const [resyncing, setResyncing] = useState(false)
  const [resettingSync, setResettingSync] = useState(false)

  async function fetchStatuses() {
    const token = await getToken()
    const results = await Promise.allSettled(
      STATUSABLE_SLUGS.map(async (slug) => {
        const res = await fetch(`${API}/v1/integrations/${slug}/status`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) return { slug, status: 'not_connected' as const, connected_at: null, last_synced_at: null, institution_name: null }
        const json = await res.json()
        return {
          slug,
          status: (json.data?.status ?? 'not_connected') as IntegrationState['status'],
          connected_at: json.data?.connected_at ?? null,
          last_synced_at: json.data?.last_synced_at ?? null,
          institution_name: json.data?.institution_name ?? null,
        }
      }),
    )
    const states: IntegrationState[] = []
    for (const r of results) {
      if (r.status === 'fulfilled') states.push(r.value)
    }
    setIntegrations(states)
    setLoading(false)
  }

  useEffect(() => { fetchStatuses() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function resyncAll() {
    setResyncing(true)
    try {
      const token = await getToken()
      const toSync = integrations.filter((i) => i.status === 'connected' || i.status === 'syncing')
      await Promise.allSettled(
        toSync.map(({ slug }) =>
          fetch(`${API}/v1/integrations/${slug}/sync`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          })
        )
      )
      await fetchStatuses()
      toast('All integrations resynced', 'success')
    } catch {
      toast('Resync failed — check individual integrations', 'error')
    } finally {
      setResyncing(false)
    }
  }

  async function resetSyncing() {
    setResettingSync(true)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/integrations/reset-syncing`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      await fetchStatuses()
      toast('Sync status reset — integrations marked connected', 'success')
    } catch {
      toast('Reset failed', 'error')
    } finally {
      setResettingSync(false)
    }
  }

  async function disconnect(slug: string) {
    setDisconnecting(slug)
    setConfirmSlug(null)
    try {
      const token = await getToken()
      await fetch(`${API}/v1/integrations/${slug}/disconnect`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      await fetchStatuses()
      toast('Integration disconnected', 'success')
    } catch {
      toast('Failed to disconnect integration', 'error')
    } finally {
      setDisconnecting(null)
    }
  }

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2].map((i) => (
          <div key={i} className="h-14 bg-brand-surface border border-brand-border rounded-sm animate-pulse" />
        ))}
      </div>
    )
  }

  const connected = integrations.filter((i) => i.status === 'connected' || i.status === 'syncing')

  if (connected.length === 0) {
    return (
      <div className="border border-brand-border rounded-sm px-4 py-6 text-center space-y-2">
        <p className="text-xs font-mono text-brand-muted">No integrations connected</p>
        <Link
          href="/dashboard/integrations"
          className="text-[10px] font-mono text-brand-secondary hover:text-brand-text transition-colors"
        >
          Connect integrations →
        </Link>
      </div>
    )
  }

  return (
    <div className="divide-y divide-brand-border border border-brand-border rounded-sm overflow-hidden">
      {connected.map(({ slug, status, connected_at, last_synced_at, institution_name }) => {
        const meta = INTEGRATION_META[slug] ?? { name: slug, desc: '' }
        const isSyncing = status === 'syncing'
        const displayName = institution_name ?? meta.name
        const providerLabel = institution_name ? meta.name : null
        return (
          <div key={slug} className="bg-brand-surface px-4 py-4 flex items-start gap-4">
            <div className="flex-1 min-w-0 space-y-1.5">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-brand-text font-medium">{displayName}</span>
                {providerLabel && (
                  <span className="text-[10px] font-mono text-brand-muted">via {providerLabel}</span>
                )}
                <span className={[
                  'text-[10px] font-mono px-2 py-0.5 rounded-sm border',
                  isSyncing
                    ? 'text-[#00a8cc] border-[#00a8cc]/30 bg-[rgba(0,168,204,0.08)]'
                    : 'text-brand-green border-brand-green/30 bg-[rgba(0,200,83,0.08)]',
                ].join(' ')}>
                  {isSyncing ? 'syncing' : 'connected'}
                </span>
              </div>
              {meta.desc && (
                <p className="text-[10px] font-mono text-brand-muted">{meta.desc}</p>
              )}
              {connected_at && (
                <p className="text-[10px] font-mono text-brand-muted">
                  Connected {new Date(connected_at).toLocaleDateString('en-GB')}
                  {last_synced_at
                    ? ` · Last sync ${new Date(last_synced_at).toLocaleDateString('en-GB')}`
                    : ''}
                </p>
              )}
            </div>

            <div className="shrink-0 flex items-center gap-2">
              {confirmSlug === slug ? (
                <>
                  <button
                    onClick={() => disconnect(slug)}
                    disabled={disconnecting === slug}
                    className="text-[10px] font-mono text-[#ff4d6d] border border-[#ff4d6d]/30 bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.15)] rounded-sm px-2 py-1 transition-colors disabled:opacity-50"
                  >
                    {disconnecting === slug ? 'Disconnecting…' : 'Confirm'}
                  </button>
                  <button
                    onClick={() => setConfirmSlug(null)}
                    className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setConfirmSlug(slug)}
                  disabled={!!disconnecting}
                  className="text-[10px] font-mono text-[#ff4d6d] border border-[#ff4d6d]/30 bg-[rgba(255,77,109,0.08)] hover:bg-[rgba(255,77,109,0.15)] rounded-sm px-2 py-1 transition-colors disabled:opacity-50"
                >
                  Disconnect
                </button>
              )}
            </div>
          </div>
        )
      })}

      <div className="bg-brand-surface px-4 py-3 flex items-center justify-between">
        <Link
          href="/dashboard/integrations"
          className="text-[10px] font-mono text-brand-muted hover:text-brand-text transition-colors"
        >
          Manage all integrations →
        </Link>
        <div className="flex items-center gap-2">
          {connected.some((i) => i.status === 'syncing') && (
            <button
              onClick={resetSyncing}
              disabled={resettingSync}
              className="text-[10px] font-mono text-[#f5a623] border border-[#f5a623]/30 bg-[rgba(245,166,35,0.08)] hover:bg-[rgba(245,166,35,0.12)] rounded-sm px-2 py-1 transition-colors disabled:opacity-50"
            >
              {resettingSync ? 'Resetting…' : 'Reset Syncing'}
            </button>
          )}
          <button
            onClick={resyncAll}
            disabled={resyncing}
            className="text-[10px] font-mono text-brand-secondary border border-brand-border bg-transparent hover:bg-brand-elevated rounded-sm px-2 py-1 transition-colors disabled:opacity-50"
          >
            {resyncing ? 'Syncing…' : 'Resync All'}
          </button>
        </div>
      </div>
    </div>
  )
}
