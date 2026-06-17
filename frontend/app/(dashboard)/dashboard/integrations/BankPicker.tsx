'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Plus } from 'lucide-react'
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

function BankCard({ bank, onViewDetail }: { bank: BankDef; onViewDetail: (b: BankDef) => void }) {
  const [error, setError] = useState(false)
  const useFallback = error || !bank.domain

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
              className={`${abbrSize(bank.abbr)} font-mono font-bold leading-none`}
              style={{ color: bank.color }}
            >
              {bank.abbr}
            </span>
          ) : (
            <Image
              unoptimized
              src={`https://www.google.com/s2/favicons?sz=128&domain=${bank.domain}`}
              alt={bank.name}
              width={40}
              height={40}
              className="object-contain"
              onError={() => setError(true)}
            />
          )}
        </div>
        <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[#00C853] border-2 border-brand-bg" />
      </div>
      <span className="text-[10px] font-mono text-brand-muted text-center leading-tight max-w-[64px] truncate">
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

  const plaidConnected = plaidStatus === 'connected' || plaidStatus === 'syncing'
  const truelayerConnected = truelayerStatus === 'connected' || truelayerStatus === 'syncing'
  const monoConnected = monoStatus === 'connected' || monoStatus === 'syncing'

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

  const fallbackAbbr =
    region === 'eu' ? 'TL' : region === 'africa' ? 'MN' : 'US'

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

  return (
    <div className="space-y-4">
      {/* Region tabs */}
      <div className="flex gap-1">
        {REGIONS.map((r) => (
          <button
            key={r.value}
            onClick={() => setRegion(r.value)}
            className={[
              'px-3 py-1 text-[10px] font-mono uppercase tracking-widest rounded-sm transition-colors',
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
              <BankCard key={bank.id} bank={bank} onViewDetail={onViewDetail} />
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
            className="px-6 py-2 text-xs font-mono text-black bg-[#00C853] rounded-sm hover:bg-[#00a844] active:scale-[0.97] transition-all disabled:opacity-40"
          >
            {connecting ? 'Connecting...' : 'Connect'}
          </button>
        </div>
      )}
    </div>
  )
}
