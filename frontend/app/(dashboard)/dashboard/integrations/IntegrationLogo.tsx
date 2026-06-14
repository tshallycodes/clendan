'use client'

import { useState } from 'react'
import Image from 'next/image'
import type { SimpleIcon } from 'simple-icons'
import * as SimpleIcons from 'simple-icons'

// Brands available in simple-icons — rendered as inline SVG
const SLUG_TO_SI_KEY: Record<string, string> = {
  quickbooks:     'siQuickbooks',
  xero:           'siXero',
  sage:           'siSage',
  stripe:         'siStripe',
  adyen:          'siAdyen',
  wise:           'siWise',
  sap:            'siSap',
  hubspot:        'siHubspot',
  gmail:          'siGmail',
  'google-drive': 'siGoogledrive',
  dropbox:        'siDropbox',
}

// Domain for Google favicon API — used for all logo sources
const SLUG_TO_DOMAIN: Record<string, string> = {
  quickbooks:     'quickbooks.intuit.com',
  xero:           'xero.com',
  sage:           'sage.com',
  stripe:         'stripe.com',
  adyen:          'adyen.com',
  wise:           'wise.com',
  sap:            'sap.com',
  hubspot:        'hubspot.com',
  gmail:          'gmail.com',
  'google-drive': 'drive.google.com',
  dropbox:        'dropbox.com',
  plaid:          'plaid.com',
  freshbooks:     'freshbooks.com',
  wave:           'waveapps.com',
  gocardless:     'gocardless.com',
  netsuite:       'netsuite.com',
  'sage-intacct': 'sageintacct.com',
  dynamics365:    'dynamics.microsoft.com',
  salesforce:     'salesforce.com',
  outlook:        'outlook.com',
  onedrive:       'onedrive.live.com',
}

interface Props {
  slug: string
  size?: number
}

function FaviconLogo({ slug, domain, size, siKey }: {
  slug: string
  domain: string
  size: number
  siKey?: string
}) {
  const [failed, setFailed] = useState(false)

  if (failed && siKey) {
    const siIcon = (SimpleIcons as unknown as Record<string, SimpleIcon | undefined>)[siKey]
    if (siIcon) {
      return (
        <svg
          role="img"
          viewBox="0 0 24 24"
          width={size}
          height={size}
          fill="var(--brand-muted)"
          className="shrink-0"
          aria-label={siIcon.title}
        >
          <path d={siIcon.path} />
        </svg>
      )
    }
  }

  if (failed) {
    const initials = slug
      .replace(/-/g, ' ')
      .split(' ')
      .map((w) => w[0]?.toUpperCase() ?? '')
      .join('')
      .slice(0, 2)
    return (
      <div className="shrink-0 flex items-center justify-center text-brand-muted font-mono font-semibold border border-brand-border rounded-sm bg-brand-surface text-[9px]" style={{ width: size, height: size }}>
        {initials}
      </div>
    )
  }

  return (
    <Image
      src={`https://www.google.com/s2/favicons?sz=128&domain=${domain}`}
      alt={slug}
      width={size}
      height={size}
      unoptimized
      onError={() => setFailed(true)}
      className="shrink-0 rounded-sm"
    />
  )
}

export function IntegrationLogo({ slug, size = 16 }: Props) {
  const domain = SLUG_TO_DOMAIN[slug]
  const siKey = SLUG_TO_SI_KEY[slug]

  if (domain) {
    return <FaviconLogo slug={slug} domain={domain} size={size} siKey={siKey} />
  }

  // Letter monogram for anything not mapped
  const initials = slug
    .replace(/-/g, ' ')
    .split(' ')
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, 2)

  return (
    <div className="shrink-0 flex items-center justify-center text-brand-muted font-mono font-semibold border border-brand-border rounded-sm bg-brand-surface w-5 h-5 text-[9px]">
      {initials}
    </div>
  )
}
