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
  connecting: boolean
  onViewDetail: (bank: BankDef) => void
  onConnect: (region: Region) => void
}

type Region = 'us' | 'eu'

const REGIONS: { label: string; value: Region }[] = [
  { label: 'US', value: 'us' },
  { label: 'EU', value: 'eu' },
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
  connecting, onViewDetail, onConnect,
}: BankPickerProps) {
  const [region, setRegion] = useState<Region>('us')

  const plaidConnected = plaidStatus === 'connected' || plaidStatus === 'syncing'
  const truelayerConnected = truelayerStatus === 'connected' || truelayerStatus === 'syncing'
  const isConnected = region === 'us' ? plaidConnected : truelayerConnected

  // Build the list of connected bank cards to show
  const connectedCards: BankDef[] = (() => {
    if (region === 'us' && plaidConnected) {
      const matched = BANKS.filter(
        (b) => b.region === 'us' && (
          (b.institution_id && b.institution_id === connectedInstitutionId) ||
          (connectedBankName && connectedBankName.toLowerCase().includes(b.name.toLowerCase()))
        )
      )
      if (matched.length > 0) return matched
      // Fallback for banks not in the predefined list
      if (connectedInstitutionId) {
        return [{
          id: connectedInstitutionId,
          name: connectedBankName || 'Connected Bank',
          abbr: (connectedBankName || 'CB').slice(0, 2).toUpperCase(),
          color: '#00C853',
          domain: '',
          provider: 'plaid' as const,
          region: 'us' as const,
        }]
      }
    }
    if (region === 'eu' && truelayerConnected) {
      if (connectedTruelayerName) {
        const matched = BANKS.filter(
          (b) => b.region === 'eu' && (
            connectedTruelayerName.toLowerCase().includes(b.name.toLowerCase()) ||
            b.name.toLowerCase().includes(connectedTruelayerName.toLowerCase())
          )
        )
        if (matched.length > 0) return matched
      }
      // Fallback
      return [{
        id: 'truelayer-connected',
        name: connectedTruelayerName || 'Connected Bank',
        abbr: (connectedTruelayerName || 'EU').slice(0, 2).toUpperCase(),
        color: '#00C853',
        domain: '',
        provider: 'truelayer' as const,
        region: 'eu' as const,
      }]
    }
    return []
  })()

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
        <div className="flex items-start gap-4 flex-wrap">
          {connectedCards.map((bank) => (
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
