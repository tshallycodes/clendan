'use client'

import type { SimpleIcon } from 'simple-icons'
import * as SimpleIcons from 'simple-icons'
import type { LucideIcon } from 'lucide-react'
import {
  Landmark, CreditCard, BookOpen, Cloud, Mail,
  Users, Database, LayoutDashboard, Link, BarChart3,
} from 'lucide-react'

// Brands available in simple-icons
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

// Brands not in simple-icons — use a semantically appropriate Lucide icon
const SLUG_TO_LUCIDE: Record<string, LucideIcon> = {
  plaid:          Landmark,
  truelayer:      Landmark,
  nordigen:       Landmark,
  codat:          Link,
  gocardless:     CreditCard,
  freshbooks:     BookOpen,
  wave:           BarChart3,
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

export function IntegrationLogo({ slug, size = 16 }: Props) {
  // 1. Try simple-icons
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

  // 2. Try Lucide semantic icon
  const LucideIcon = SLUG_TO_LUCIDE[slug]
  if (LucideIcon) {
    return (
      <LucideIcon
        width={size}
        height={size}
        strokeWidth={1.5}
        className="shrink-0 text-[#a0b8a0]"
      />
    )
  }

  // 3. Letter monogram fallback
  const initials = slug
    .replace(/-/g, ' ')
    .split(' ')
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, 2)

  return (
    <div
      className="shrink-0 flex items-center justify-center text-[#4a6a4a] font-mono font-semibold border border-[#1a2a1a] rounded-sm bg-[#111111] w-5 h-5 text-[9px]"
    >
      {initials}
    </div>
  )
}
