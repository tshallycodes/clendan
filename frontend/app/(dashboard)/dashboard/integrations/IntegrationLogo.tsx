'use client'

import type { SimpleIcon } from 'simple-icons'
import * as SimpleIcons from 'simple-icons'

const SLUG_TO_KEY: Record<string, string> = {
  quickbooks:       'siQuickbooks',
  xero:             'siXero',
  freshbooks:       'siFreshbooks',
  sage:             'siSage',
  wave:             'siWave',
  plaid:            'siPlaid',
  truelayer:        'siTruelayer',
  codat:            'siCodat',
  nordigen:         'siNordigen',
  stripe:           'siStripe',
  gocardless:       'siGocardless',
  adyen:            'siAdyen',
  wise:             'siWise',
  netsuite:         'siNetsuite',
  sap:              'siSap',
  dynamics365:      'siMicrosoftdynamics365',
  'sage-intacct':   'siSageintacct',
  salesforce:       'siSalesforce',
  hubspot:          'siHubspot',
  gmail:            'siGmail',
  outlook:          'siMicrosoftoutlook',
  'google-drive':   'siGoogledrive',
  dropbox:          'siDropbox',
  onedrive:         'siMicrosoftonedrive',
}

interface Props {
  slug: string
  size?: number
}

export function IntegrationLogo({ slug, size = 16 }: Props) {
  const key = SLUG_TO_KEY[slug]
  const icon = key
    ? (SimpleIcons as unknown as Record<string, SimpleIcon | undefined>)[key]
    : undefined

  if (!icon) {
    const initials = slug
      .replace(/-/g, ' ')
      .split(' ')
      .map((w) => w[0]?.toUpperCase() ?? '')
      .join('')
      .slice(0, 2)

    return (
      <div
        style={{ width: size, height: size, fontSize: Math.floor(size * 0.45) }}
        className="shrink-0 flex items-center justify-center text-[#4a6a4a] font-mono font-semibold border border-[#1a2a1a] rounded-sm bg-[#111111]"
      >
        {initials}
      </div>
    )
  }

  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="#a0b8a0"
      className="shrink-0"
      aria-label={icon.title}
    >
      <path d={icon.path} />
    </svg>
  )
}
