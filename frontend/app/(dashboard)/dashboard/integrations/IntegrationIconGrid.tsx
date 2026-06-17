'use client'

import { useState } from 'react'
import Image from 'next/image'
import { IntegrationDef, IntegrationStatus } from './types'

const DOMAINS: Record<string, string> = {
  quickbooks:     'quickbooks.intuit.com',
  xero:           'xero.com',
  freshbooks:     'freshbooks.com',
  sage:           'sage.com',
  wave:           'waveapps.com',
  stripe:         'stripe.com',
  gocardless:     'gocardless.com',
  adyen:          'adyen.com',
  wise:           'wise.com',
  square:         'squareup.com',
  netsuite:       'netsuite.com',
  sap:            'sap.com',
  dynamics365:    'dynamics.microsoft.com',
  'sage-intacct': 'sageintacct.com',
  salesforce:     'salesforce.com',
  hubspot:        'hubspot.com',
  gmail:          'gmail.com',
  outlook:        'outlook.com',
  'google-drive': 'drive.google.com',
  dropbox:        'dropbox.com',
  onedrive:       'onedrive.live.com',
}

function IntegrationIcon({ slug, name }: { slug: string; name: string }) {
  const [failed, setFailed] = useState(false)
  const domain = DOMAINS[slug]

  if (!domain || failed) {
    const initials = slug
      .replace(/-/g, ' ')
      .split(' ')
      .map((w) => w[0]?.toUpperCase() ?? '')
      .join('')
      .slice(0, 2)
    return (
      <div className="w-full h-full flex items-center justify-center bg-brand-elevated">
        <span className="text-sm font-mono font-bold text-brand-text">{initials}</span>
      </div>
    )
  }

  return (
    <Image
      unoptimized
      src={`https://www.google.com/s2/favicons?sz=128&domain=${domain}`}
      alt={name}
      width={40}
      height={40}
      className="object-contain"
      onError={() => setFailed(true)}
    />
  )
}

interface Props {
  integrations: IntegrationDef[]
  statuses: Record<string, IntegrationStatus>
  onViewDetail: (intg: IntegrationDef) => void
}

export function IntegrationIconGrid({ integrations, statuses, onViewDetail }: Props) {
  return (
    <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-4">
      {integrations.map((intg) => {
        const status = statuses[intg.slug] ?? 'not_connected'
        const isConnected = status === 'connected' || status === 'syncing'
        return (
          <button
            key={intg.slug}
            onClick={() => !intg.comingSoon && onViewDetail(intg)}
            disabled={intg.comingSoon}
            className={[
              'flex flex-col items-center gap-1.5 group',
              intg.comingSoon ? 'cursor-default opacity-50' : 'cursor-pointer',
            ].join(' ')}
            title={intg.comingSoon ? `${intg.name} — Coming Soon` : intg.name}
          >
            <div className="relative w-16 h-16">
              <div className={[
                'w-full h-full rounded-sm flex items-center justify-center overflow-hidden bg-white dark:bg-transparent transition-all',
                !intg.comingSoon && 'group-hover:ring-1 group-hover:ring-[#00C853]/40',
              ].filter(Boolean).join(' ')}>
                <IntegrationIcon slug={intg.slug} name={intg.name} />
              </div>
              {isConnected && (
                <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[#00C853] border-2 border-brand-bg" />
              )}
              {intg.comingSoon && (
                <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 text-[8px] font-mono uppercase tracking-wider text-brand-muted bg-brand-elevated border border-brand-border px-1 py-0.5 rounded-sm whitespace-nowrap">
                  soon
                </span>
              )}
            </div>
            <span className="text-[10px] font-mono text-brand-muted text-center leading-tight max-w-[64px] truncate">
              {intg.name}
            </span>
          </button>
        )
      })}
    </div>
  )
}
