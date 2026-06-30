'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Plus } from '@phosphor-icons/react'
import { BANKS, BankDef } from './banks-data'
import { IntegrationStatus } from './types'

interface BankPickerProps {
  plaidStatus: IntegrationStatus
  connectedInstitutionId: string | null
  connectedBankName: string | null
  truelayerStatus: IntegrationStatus
  connectedTruelayerName: string | null
  monoStatus: IntegrationStatus
  connectedMonoName: string | null
  connecting: boolean
  onViewDetail: (bank: BankDef) => void
  onConnect: (region: Region) => void
}

type Region = 'us' | 'eu' | 'africa'

const REGIONS: { label: string; value: Region }[] = [
  { label: 'US', value: 'us' },
  { label: 'EU', value: 'eu' },
  { label: 'Africa', value: 'africa' },
]

function abbrSize(abbr: string): string {
  if (abbr.length <= 2) return 'text-base'
  if (abbr.length === 3) return 'text-sm'
  return 'text-xs'
}

function BankCard({ bank, syncError, onViewDetail }: { bank: BankDef; syncError?: boolean; onViewDetail: (b: BankDef) => void }) {
  const [imgError, setImgError] = useState(false)
  const useFallback = imgError || !bank.domain

  return (
    <button
      onClick={() => onViewDetail(bank)}
      className="flex flex-col items-center gap-1.5 group cursor-pointer"
      title={bank.name}
    >
      <div className="relative w-16 h-16">
        <div
          className="w-full h-full rounded-sm flex items-center justify-center overflow-hidden border border-brand-border group-hover:ring-1 group-hover:ring-[#00C853]/40 group-hover:border-[#00C853]/30 transition-all bg-brand-surface"
        >
          {useFallback ? (
            <span
              className={`${abbrSize(bank.abbr)} font-body font-bold leading-none`}
              style={{ color: bank.color }}
            >
              {bank.abbr}
            </span>
          ) : (
            <Image
              unoptimized
              src={`https://www.google.com/s2/favicons?sz=128&domain=${bank.domain}`}
              alt={bank.name}
              width={56}
              height={56}
              className="object-contain"
              onError={() => setImgError(true)}
            />
          )}
        </div>
        <span
          className="absolute -top-1 -right-1 w-3 h-3 rounded-full border-2 border-brand-bg"
          style={{ background: syncError ? '#ff4d6d' : '#00C853' }}
        />
      </div>
      <span className="text-[11px] font-body text-brand-muted text-center leading-tight max-w-[64px] truncate">
        {bank.name}
      </span>
    </button>
  )
}

export function BankPicker({
  plaidStatus, connectedInstitutionId, connectedBankName,
  truelayerStatus, connectedTruelayerName,
  monoStatus, connectedMonoName,
  connecting, onViewDetail, onConnect,
}: BankPickerProps) {
  const [region, setRegion] = useState<Region>('us')

  const plaidConnected = plaidStatus === 'connected' || plaidStatus === 'syncing' || plaidStatus === 'error'
  const truelayerConnected = truelayerStatus === 'connected' || truelayerStatus === 'syncing' || truelayerStatus === 'error'
  const monoConnected = monoStatus === 'connected' || monoStatus === 'syncing' || monoStatus === 'error'

  const isConnected =
    (region === 'us' && plaidConnected) ||
    (region === 'eu' && truelayerConnected) ||
    (region === 'africa' && monoConnected)

  // Try to find a specific bank card by name match
  const connectedCards: BankDef[] = (() => {
    if (region === 'us' && plaidConnected) {
      return BANKS.filter(
        (b) => b.region === 'us' && (
          (b.institution_id && b.institution_id === connectedInstitutionId) ||
          (connectedBankName && connectedBankName.toLowerCase().includes(b.name.toLowerCase()))
        )
      )
    }
    if (region === 'eu' && truelayerConnected && connectedTruelayerName) {
      return BANKS.filter(
        (b) => b.region === 'eu' && (
          connectedTruelayerName.toLowerCase().includes(b.name.toLowerCase()) ||
          b.name.toLowerCase().includes(connectedTruelayerName.toLowerCase())
        )
      )
    }
    if (region === 'africa' && monoConnected && connectedMonoName) {
      return BANKS.filter(
        (b) => b.region === 'africa' && (
          connectedMonoName.toLowerCase().includes(b.name.toLowerCase()) ||
          b.name.toLowerCase().includes(connectedMonoName.toLowerCase())
        )
      )
    }
    return []
  })()

  // When connected but no specific card matched, derive a display name
  const fallbackName =
    region === 'eu' ? (connectedTruelayerName ?? 'Bank')
    : region === 'africa' ? (connectedMonoName ?? 'Bank')
    : (connectedBankName ?? 'Bank')

  const provider: BankDef['provider'] =
    region === 'eu' ? 'truelayer' : region === 'africa' ? 'mono' : 'plaid'

  function nameToAbbr(name: string | null, fallback: string): string {
    if (!name) return fallback
    return name.split(/\s+/).map((w) => w.replace(/[^A-Za-z]/g, '')[0] ?? '').filter(Boolean).join('').toUpperCase().slice(0, 3) || fallback
  }

  const fallbackAbbr =
    region === 'eu' ? nameToAbbr(connectedTruelayerName, 'TL')
    : region === 'africa' ? nameToAbbr(connectedMonoName, 'MN')
    : nameToAbbr(connectedBankName, 'PL')

  const fallbackCard: BankDef = {
    id: `${provider}-generic`,
    name: fallbackName,
    abbr: fallbackAbbr,
    color: '#888888',
    domain: '',
    provider,
    region: region === 'us' ? 'us' : region === 'eu' ? 'eu' : 'africa',
  }

  const displayCards = connectedCards.length > 0 ? connectedCards : (isConnected ? [fallbackCard] : [])

  const regionStatus =
    region === 'eu' ? truelayerStatus
    : region === 'africa' ? monoStatus
    : plaidStatus
  const isSyncError = regionStatus === 'error'

  return (
    <div className="space-y-4">
      {/* Region tabs */}
      <div className="flex gap-1">
        {REGIONS.map((r) => (
          <button
            key={r.value}
            onClick={() => setRegion(r.value)}
            className={[
              'px-3 py-1 text-[11px] font-body uppercase tracking-widest rounded-sm transition-colors',
              region === r.value
                ? 'bg-brand-surface border border-brand-border text-brand-text'
                : 'text-brand-muted hover:text-brand-secondary',
            ].join(' ')}
          >
            {r.label}
          </button>
        ))}
      </div>

      {isConnected ? (
        /* Connected state — show only connected banks + add button */
        <div className="space-y-3">
          <div className="flex items-start gap-4 flex-wrap">
            {displayCards.map((bank) => (
              <BankCard key={bank.id} bank={bank} syncError={isSyncError} onViewDetail={onViewDetail} />
            ))}

            {/* Add another bank */}
            <button
              onClick={() => onConnect(region)}
              disabled={connecting}
              className="flex flex-col items-center gap-1.5 cursor-pointer disabled:opacity-40"
              title="Connect another bank"
            >
              <div className="w-16 h-16 rounded-sm flex items-center justify-center bg-[#00C853] hover:bg-[#00a844] active:scale-[0.97] transition-all">
                <Plus size={20} className="text-black" />
              </div>
            </button>
          </div>

        </div>
      ) : (
        /* Not connected — single connect button */
        <div className="flex justify-center py-4">
          <button
            onClick={() => onConnect(region)}
            disabled={connecting}
            className="px-6 py-2 text-xs font-body text-black bg-[#00C853] rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all disabled:opacity-40"
          >
            {connecting ? 'Connecting...' : 'Connect'}
          </button>
        </div>
      )}
    </div>
  )
}
