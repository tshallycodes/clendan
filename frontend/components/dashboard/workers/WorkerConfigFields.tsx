'use client'

const inputClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text outline-none transition-colors'
const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

interface FieldDef {
  key: string
  label: string
  type: 'number' | 'select' | 'text'
  unit?: string
  placeholder?: string
  default: number | string
  step?: number
  min?: number
  max?: number
  options?: string[]
  penceDisplay?: boolean
}

const WORKER_FIELDS: Record<string, FieldDef[]> = {
  invoice_processing: [
    { key: 'auto_threshold',      type: 'number', label: 'Auto-approve under',  unit: 'pence', default: 50000,  penceDisplay: true },
    { key: 'approve_threshold',   type: 'number', label: 'Block above',          unit: 'pence', default: 500000, penceDisplay: true },
    { key: 'allowed_currencies',  type: 'text',   label: 'Allowed currencies',   placeholder: 'GBP, USD, EUR',  default: 'GBP, USD' },
  ],
  ai_accountant: [
    { key: 'auto_confidence',    type: 'number', label: 'Auto-categorise above confidence', unit: '0 – 1', default: 0.85, step: 0.01, min: 0, max: 1 },
    { key: 'review_confidence',  type: 'number', label: 'Flag for review below confidence', unit: '0 – 1', default: 0.50, step: 0.01, min: 0, max: 1 },
  ],
  receipt_processing: [
    { key: 'receipt_required_above', type: 'number', label: 'Receipt required above',     unit: 'pence', default: 2500,  penceDisplay: true },
    { key: 'max_single_expense',     type: 'number', label: 'Block single expense above', unit: 'pence', default: 25000, penceDisplay: true },
  ],
  reconciliation: [
    { key: 'amount_tolerance_pence', type: 'number', label: 'Amount tolerance',      unit: 'pence', default: 100, penceDisplay: true },
    { key: 'staleness_days',         type: 'number', label: 'Flag unmatched after',  unit: 'days',  default: 30 },
  ],
  expense_control: [
    { key: 'monthly_limit_per_employee', type: 'number', label: 'Monthly limit per employee', unit: 'pence', default: 100000, penceDisplay: true },
    { key: 'receipt_required_above',     type: 'number', label: 'Receipt required above',     unit: 'pence', default: 2500,   penceDisplay: true },
    { key: 'blocked_categories',         type: 'text',   label: 'Blocked categories',         placeholder: 'entertainment, gambling', default: '' },
  ],
  collections: [
    { key: 'first_reminder_days', type: 'number', label: 'First reminder after', unit: 'days overdue', default: 7  },
    { key: 'escalate_days',       type: 'number', label: 'Escalate after',       unit: 'days overdue', default: 30 },
    { key: 'legal_days',          type: 'number', label: 'Legal action after',   unit: 'days overdue', default: 60 },
  ],
  fraud_detection: [
    { key: 'risk_score_block',        type: 'number', label: 'Block above risk score',         unit: '0 – 1',   default: 0.85, step: 0.01, min: 0, max: 1 },
    { key: 'velocity_max_txns',       type: 'number', label: 'Max transactions per window',    unit: 'count',   default: 10 },
    { key: 'velocity_window_minutes', type: 'number', label: 'Velocity window',                unit: 'minutes', default: 60 },
  ],
  treasury: [
    { key: 'min_balance_alert',        type: 'number', label: 'Alert when balance below', unit: 'pence', default: 1000000, penceDisplay: true },
    { key: 'cash_runway_warning_days', type: 'number', label: 'Warn when runway below',   unit: 'days',  default: 90 },
    { key: 'forecast_horizon_days',    type: 'number', label: 'Forecast horizon',         unit: 'days',  default: 30 },
  ],
  revenue_recognition: [
    { key: 'accounting_standard',  type: 'select', label: 'Accounting standard',      options: ['ASC 606', 'IFRS 15'],      default: 'ASC 606'   },
    { key: 'recognition_method',   type: 'select', label: 'Default recognition',      options: ['at-point', 'over-time'],   default: 'at-point'  },
  ],
  credit_underwriting: [
    { key: 'min_credit_score', type: 'number', label: 'Minimum credit score',        unit: 'score',   default: 650  },
    { key: 'max_dti_ratio',    type: 'number', label: 'Max debt-to-income ratio',    unit: '0 – 1',   default: 0.43, step: 0.01, min: 0, max: 1 },
  ],
  compliance: [
    { key: 'report_above_minor', type: 'number', label: 'Report transactions above', unit: 'pence',   default: 1000000, penceDisplay: true },
    { key: 'frameworks',         type: 'text',   label: 'Regulatory frameworks',     placeholder: 'AML, KYC, GDPR', default: 'AML, KYC' },
  ],
}

export function getDefaultConfig(workerType: string): Record<string, unknown> {
  return Object.fromEntries((WORKER_FIELDS[workerType] ?? []).map(f => [f.key, f.default]))
}

interface WorkerConfigFieldsProps {
  workerType: string
  config: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

export function WorkerConfigFields({ workerType, config, onChange }: WorkerConfigFieldsProps) {
  const fields = WORKER_FIELDS[workerType] ?? []
  if (fields.length === 0) return null

  return (
    <div className="space-y-3 border-t border-brand-border pt-3">
      <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest">Worker Settings</p>
      {fields.map((field) => {
        const value = config[field.key] ?? field.default

        if (field.type === 'select') {
          return (
            <div key={field.key} className="space-y-1.5">
              <label className={labelClass}>{field.label}</label>
              <select value={value as string} onChange={e => onChange(field.key, e.target.value)} className={inputClass}>
                {field.options!.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
          )
        }

        if (field.type === 'text') {
          return (
            <div key={field.key} className="space-y-1.5">
              <label className={labelClass}>{field.label}</label>
              <input type="text" value={value as string} placeholder={field.placeholder} onChange={e => onChange(field.key, e.target.value)} className={inputClass} />
            </div>
          )
        }

        return (
          <div key={field.key} className="space-y-1.5">
            <label className={labelClass}>{field.label} <span className="normal-case opacity-60">({field.unit})</span></label>
            <input
              type="number"
              value={value as number}
              min={field.min ?? 0}
              max={field.max}
              step={field.step ?? 1}
              onChange={e => onChange(field.key, field.step ? parseFloat(e.target.value) : parseInt(e.target.value, 10))}
              className={inputClass}
            />
            {field.penceDisplay && (
              <p className="text-[10px] font-mono text-brand-muted">£{((value as number) / 100).toFixed(2)}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
