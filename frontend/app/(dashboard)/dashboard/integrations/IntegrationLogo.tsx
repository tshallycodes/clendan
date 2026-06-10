'use client'

import { useState } from 'react'
import Image from 'next/image'
import type { SimpleIcon } from 'simple-icons'
import * as SimpleIcons from 'simple-icons'
import type { LucideIcon } from 'lucide-react'
import {
  Landmark, CreditCard, BookOpen, Cloud, Mail,
  Users, Database, LayoutDashboard, Link, BarChart3,
} from 'lucide-react'

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

// Domain for Clearbit logo API — used when simple-icons has no entry
const SLUG_TO_DOMAIN: Record<string, string> = {
  plaid:          'plaid.com',
  freshbooks:     'freshbooks.com',
  wave:           'waveapps.com',
  truelayer:      'truelayer.com',
  codat:          'codat.io',
  nordigen:       'bankaccountdata.gocardless.com',
  gocardless:     'gocardless.com',
  netsuite:       'netsuite.com',
  'sage-intacct': 'sageintacct.com',
  dynamics365:    'dynamics.microsoft.com',
  salesforce:     'salesforce.com',
  outlook:        'outlook.com',
  onedrive:       'onedrive.live.com',
}

// Lucide fallback if Clearbit image fails to load
const SLUG_TO_LUCIDE: Record<string, LucideIcon> = {
  plaid:          Landmark,
  freshbooks:     BookOpen,
  wave:           BarChart3,
  truelayer:      Landmark,
  codat:          Link,
  nordigen:       Landmark,
  gocardless:     CreditCard,
  netsuite:       Database,
  'sage-intacct': Database,
  dynamics365:    LayoutDashboard,
  salesforce:     Users,
  outlook:        Mail,
  onedrive:       Cloud,
}

interface Props {
  slug: string
  size?: number
}

function ClearbitLogo({ slug, domain, size, fallback: Fallback }: {
  slug: string
  domain: string
  size: number
  fallback: LucideIcon
}) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <Fallback
        width={size}
        height={size}
        strokeWidth={1.5}
        className="shrink-0 text-[#a0b8a0]"
      />
    )
  }

  return (
    <Image
      src={`https://logo.clearbit.com/${domain}`}
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
  // 1. Inline SVG from simple-icons
  const siKey = SLUG_TO_SI_KEY[slug]
  const siIcon = siKey
    ? (SimpleIcons as unknown as Record<string, SimpleIcon | undefined>)[siKey]
    : undefined

  if (siIcon) {
    return (
      <svg
        role="img"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="#a0b8a0"
        className="shrink-0"
        aria-label={siIcon.title}
      >
        <path d={siIcon.path} />
      </svg>
    )
  }

  // 2. Clearbit logo with Lucide fallback on error
  const domain = SLUG_TO_DOMAIN[slug]
  const LucideFallback = SLUG_TO_LUCIDE[slug]
  if (domain && LucideFallback) {
    return (
      <ClearbitLogo
        slug={slug}
        domain={domain}
        size={size}
        fallback={LucideFallback}
      />
    )
  }

  // 3. Letter monogram for anything not mapped
  const initials = slug
    .replace(/-/g, ' ')
    .split(' ')
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, 2)

  return (
    <div className="shrink-0 flex items-center justify-center text-[#4a6a4a] font-mono font-semibold border border-[#1a2a1a] rounded-sm bg-[#111111] w-5 h-5 text-[9px]">
      {initials}
    </div>
  )
}
