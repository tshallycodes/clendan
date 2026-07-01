'use client'

import { useState } from 'react'
import { Info } from '@phosphor-icons/react'
import { Select } from '@/components/ui/Select'
import { NumberInput } from '@/components/ui/NumberInput'
import { useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'
import { WORKER_FIELDS, getDefaultConfig } from './tool-config-data'

export { getDefaultConfig }

const inputClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-body text-brand-text outline-none transition-colors'
const labelClass = 'text-[11px] font-body text-brand-muted uppercase tracking-widest'

interface ToolConfigFieldsProps {
  toolType: string
  config: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
  dynamicOptions?: Record<string, string[]>
}

function InfoIcon({ fieldKey, open, onToggle }: {
  fieldKey: string
  open: boolean
  onToggle: (key: string) => void
}) {
  return (
    <button
      type="button"
      onClick={() => onToggle(fieldKey)}
      aria-label="What does this setting do?"
      className={`ml-2 shrink-0 transition-all ${
        open ? 'text-[#00a8cc]' : 'text-[rgba(0,168,204,0.5)] hover:text-[#00a8cc]'
      }`}
    >
      <Info size={13} weight="fill" />
    </button>
  )
}

export function ToolConfigFields({ toolType, config, onChange, dynamicOptions }: ToolConfigFieldsProps) {
  const fields = WORKER_FIELDS[toolType] ?? []
  const [openHint, setOpenHint] = useState<string | null>(null)
  const { currency } = useCurrency()
  const currencySymbol = CURRENCY_MAP[currency]?.symbol ?? currency

  if (fields.length === 0) return null

  function toggleHint(key: string) {
    setOpenHint(prev => prev === key ? null : key)
  }

  return (
    <div className="space-y-3 border-t border-brand-border pt-3">
      <p className={labelClass}>Tool Settings</p>
      {fields.map((field) => {
        if (field.showWhen && !field.showWhen(config)) return null
        const value = config[field.key] ?? field.default
        const hintOpen = openHint === field.key

        if (field.type === 'boolean') {
          const isOn = value as boolean
          return (
            <div key={field.key}>
              <div className="flex items-start justify-between gap-6">
                <span className={`${labelClass} flex items-center flex-1 min-w-0`}>
                  <span className="leading-relaxed">{field.label}</span>
                  {field.description && (
                    <InfoIcon fieldKey={field.key} open={hintOpen} onToggle={toggleHint} />
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => onChange(field.key, !isOn)}
                  className={`shrink-0 text-xs font-body px-3 py-1 rounded-sm border transition-colors ${isOn ? 'border-brand-green text-brand-green' : 'border-brand-border text-brand-muted'}`}
                >
                  {isOn ? 'ON' : 'OFF'}
                </button>
              </div>
              {hintOpen && field.description && (
                <p className="mt-1.5 text-[11px] font-body text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
                  {field.description}
                </p>
              )}
            </div>
          )
        }

        if (field.type === 'select') {
          return (
            <div key={field.key} className="space-y-1.5">
              <label className={`${labelClass} flex items-center`}>
                {field.label}
                {field.description && (
                  <InfoIcon fieldKey={field.key} open={hintOpen} onToggle={toggleHint} />
                )}
              </label>
              <Select
                value={value as string}
                onChange={v => onChange(field.key, v)}
                options={field.options!.map(opt => ({
                  value: opt,
                  label: opt.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                }))}
              />
              {hintOpen && field.description && (
                <p className="text-[11px] font-body text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
                  {field.description}
                </p>
              )}
            </div>
          )
        }

        if (field.type === 'multiselect') {
          const selected = (Array.isArray(value) ? value : []) as string[]
          const opts = dynamicOptions?.[field.key] ?? field.options ?? []
          return (
            <div key={field.key} className="space-y-1.5">
              <label className={`${labelClass} flex items-center`}>
                {field.label}
                {field.description && (
                  <InfoIcon fieldKey={field.key} open={hintOpen} onToggle={toggleHint} />
                )}
              </label>
              {opts.length === 0 ? (
                <p className="text-[11px] font-body text-brand-muted bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
                  No connected integrations. Connect one via Integrations first.
                </p>
              ) : (
                <div className="space-y-1">
                  {opts.map(opt => {
                    const isChecked = selected.includes(opt)
                    return (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => {
                          const next = isChecked
                            ? selected.filter(v => v !== opt)
                            : [...selected, opt]
                          onChange(field.key, next)
                        }}
                        className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-sm border text-left transition-colors ${
                          isChecked ? 'bg-brand-elevated border-brand-border' : 'bg-brand-bg border-brand-border hover:bg-brand-elevated'
                        }`}
                      >
                        <span className={`w-3.5 h-3.5 rounded-[2px] border flex items-center justify-center shrink-0 transition-colors ${
                          isChecked ? 'bg-[#00C853] border-[#00C853]' : 'bg-brand-bg border-brand-border'
                        }`}>
                          {isChecked && (
                            <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                              <path d="M1 3L3 5L7 1" stroke="black" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          )}
                        </span>
                        <span className="text-[12px] font-body text-brand-text">
                          {opt.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
              {hintOpen && field.description && (
                <p className="text-[11px] font-body text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
                  {field.description}
                </p>
              )}
            </div>
          )
        }

        if (field.type === 'text') {
          return (
            <div key={field.key} className="space-y-1.5">
              <label className={`${labelClass} flex items-center`}>
                {field.label}
                {field.description && (
                  <InfoIcon fieldKey={field.key} open={hintOpen} onToggle={toggleHint} />
                )}
              </label>
              <input
                type="text"
                value={value as string}
                placeholder={field.placeholder}
                onChange={e => onChange(field.key, e.target.value)}
                className={inputClass}
              />
              {hintOpen && field.description && (
                <p className="text-[11px] font-body text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
                  {field.description}
                </p>
              )}
            </div>
          )
        }

        return (
          <div key={field.key} className="space-y-1.5">
            <label className={`${labelClass} flex items-center`}>
              {field.label}
              {field.unit && <span className="normal-case opacity-60"> ({field.unit})</span>}
              {field.description && (
                <InfoIcon fieldKey={field.key} open={hintOpen} onToggle={toggleHint} />
              )}
            </label>
            <NumberInput
              value={value as number}
              min={field.min ?? 0}
              max={field.max}
              step={field.step ?? 1}
              onChange={v => onChange(field.key, v)}
            />
            {field.penceDisplay && (
              <p className="text-[11px] font-body text-brand-muted">{currencySymbol}{((value as number) / 100).toFixed(2)}</p>
            )}
            {hintOpen && field.description && (
              <p className="text-[11px] font-body text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
                {field.description}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
