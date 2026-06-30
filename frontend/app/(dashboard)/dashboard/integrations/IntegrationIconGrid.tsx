'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import { IntegrationDef, IntegrationStatus } from './types'

function GoogleDriveSVG({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 87.3 78" fill="none" aria-label="Google Drive">
      <path d="M6.6 66.85 10.45 73.5c.8 1.4 1.95 2.5 3.3 3.3L27.5 53H0c0 1.55.4 3.1 1.2 4.5z" fill="#0066DA"/>
      <path d="M43.65 25 29.9 1.2c-1.35.8-2.5 1.9-3.3 3.3L1.2 48.5C.4 49.9 0 51.45 0 53h27.5z" fill="#00AC47"/>
      <path d="M73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75L86.1 57.5c.8-1.4 1.2-2.95 1.2-4.5H59.8z" fill="#EA4335"/>
      <path d="M43.65 25 57.4 1.2c-1.35-.8-2.9-1.2-4.5-1.2H34.4c-1.6 0-3.15.45-4.5 1.2z" fill="#00832D"/>
      <path d="M59.8 53H27.5L13.75 76.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684FC"/>
      <path d="M73.4 26.5 60.7 4.5c-.8-1.4-1.95-2.5-3.3-3.3L43.65 25 59.8 53h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#FFBA00"/>
    </svg>
  )
}

function DropboxSVG({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 43 40" fill="#0061FF" aria-label="Dropbox">
      <path d="M12.5 0 0 8l8.5 7L21 7l12.5 8 8.5-7L29.5 0 21 6.3z"/>
      <path d="M0 22.5l12.5 8L21 24l8.5 6.5 12.5-8-8.5-7L21 22.5l-8.5-7z"/>
      <path d="M12.5 32.5 21 39l8.5-6.5v-6.5L21 32.5l-8.5-6.5z"/>
    </svg>
  )
}

function GmailSVG({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-label="Gmail">
      <path d="M20 4H4C2.9 4 2 4.9 2 6v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z" fill="#EA4335"/>
    </svg>
  )
}

const INLINE_ICONS: Partial<Record<string, (size: number) => React.ReactElement>> = {
  'google-drive': (size) => <GoogleDriveSVG size={size} />,
  dropbox:        (size) => <DropboxSVG size={size} />,
  gmail:          (size) => <GmailSVG size={size} />,
}

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
  outlook:        'outlook.com',
  onedrive:       'onedrive.live.com',
  plaid:          'plaid.com',
  mono:           'mono.co',
}

function IntegrationIcon({ slug, name }: { slug: string; name: string }) {
  const [failed, setFailed] = useState(false)

  const inlineIcon = INLINE_ICONS[slug]
  if (inlineIcon) return inlineIcon(40)

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
        <span className="text-sm font-body font-bold text-brand-text">{initials}</span>
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
                <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 text-[8px] font-body uppercase tracking-wider text-brand-muted bg-brand-elevated border border-brand-border px-1 py-0.5 rounded-sm whitespace-nowrap">
                  soon
                </span>
              )}
            </div>
            <span className="text-[10px] font-body text-brand-muted text-center leading-tight max-w-[64px] truncate">
              {intg.name}
            </span>
          </button>
        )
      })}
    </div>
  )
}
