'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import type { SimpleIcon } from 'simple-icons'
import * as SimpleIcons from 'simple-icons'

// Crisp inline SVGs for brands where the favicon API produces blurry results
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

const INLINE_SVG: Partial<Record<string, (size: number) => React.ReactElement>> = {
  'google-drive': (size) => <GoogleDriveSVG size={size} />,
  dropbox:        (size) => <DropboxSVG size={size} />,
  gmail:          (size) => <GmailSVG size={size} />,
}

// Brands available in simple-icons — rendered as inline SVG
const SLUG_TO_SI_KEY: Record<string, string> = {
  quickbooks:     'siQuickbooks',
  xero:           'siXero',
  sage:           'siSage',
  stripe:         'siStripe',
  square:         'siSquare',
  adyen:          'siAdyen',
  wise:           'siWise',
  sap:            'siSap',
  hubspot:        'siHubspot',
}

// Domain for Google favicon API — used for all logo sources
const SLUG_TO_DOMAIN: Record<string, string> = {
  quickbooks:     'quickbooks.intuit.com',
  xero:           'xero.com',
  sage:           'sage.com',
  stripe:         'stripe.com',
  square:         'squareup.com',
  adyen:          'adyen.com',
  wise:           'wise.com',
  sap:            'sap.com',
  hubspot:        'hubspot.com',
  plaid:          'plaid.com',
  mono:           'mono.co',
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
      <div className="shrink-0 flex items-center justify-center text-brand-muted font-body font-semibold border border-brand-border rounded-sm bg-brand-surface text-[9px]" style={{ width: size, height: size }}>
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
  const inlineSvg = INLINE_SVG[slug]
  if (inlineSvg) return inlineSvg(size)

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
    <div className="shrink-0 flex items-center justify-center text-brand-muted font-body font-semibold border border-brand-border rounded-sm bg-brand-surface w-5 h-5 text-[9px]">
      {initials}
    </div>
  )
}
