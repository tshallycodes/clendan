'use client'

import { useState } from 'react'
import Image from 'next/image'
import { BANKS, BankDef } from './banks-data'

interface BankPickerProps {
  connectedInstitutionId: string | null
  connecting: boolean
  onViewDetail: (bank: BankDef) => void
}

type Region = 'all' | 'us' | 'uk' | 'eu'

const REGIONS: { label: string; value: Region }[] = [
  { label: 'All', value: 'all' },
  { label: 'US', value: 'us' },
  { label: 'UK', value: 'uk' },
  { label: 'EU', value: 'eu' },
]

function abbrSize(abbr: string): string {
  if (abbr.length <= 2) return 'text-base'
  if (abbr.length === 3) return 'text-sm'
  return 'text-xs'
}

function BankLogo({ bank }: { bank: BankDef }) {
  const [error, setError] = useState(false)

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center" style={{ backgroundColor: bank.color }}>
        <span className={`${abbrSize(bank.abbr)} font-mono font-bold text-white leading-none`}>
          {bank.abbr}
        </span>
      </div>
    )
  }

  return (
    <Image
      unoptimized
      src={`https://www.google.com/s2/favicons?sz=128&domain=${bank.domain}`}
      alt={bank.name}
      width={40}
      height={40}
      className="object-contain"
      onError={() => setError(true)}
    />
  )
}

export function BankPicker({ connectedInstitutionId, connecting, onViewDetail }: BankPickerProps) {
  const [region, setRegion] = useState<Region>('all')

  const filtered = region === 'all' ? BANKS : BANKS.filter((b) => b.region === region)

  return (
    <div className="space-y-4">
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

      <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-4">
        {filtered.map((bank) => {
          const isConnected = !!(bank.institution_id && bank.institution_id === connectedInstitutionId)
          return (
            <button
              key={bank.id}
              onClick={() => onViewDetail(bank)}
              className="flex flex-col items-center gap-1.5 group cursor-pointer"
              title={bank.name}
            >
              <div className="relative w-16 h-16">
                <div className="w-full h-full rounded-sm flex items-center justify-center overflow-hidden bg-white border border-[#2a2a2a] group-hover:ring-1 group-hover:ring-[#00C853]/40 group-hover:border-[#00C853]/30 transition-all relative">
                  <BankLogo bank={bank} />
                </div>
                {isConnected && (
                  <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[#00C853] border-2 border-[#0a0a0a]" />
                )}
              </div>
              <span className="text-[10px] font-mono text-brand-muted text-center leading-tight max-w-[64px] truncate">
                {bank.name}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
