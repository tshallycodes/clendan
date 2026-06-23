'use client'

import { Select } from '@/components/ui/Select'
import { NumberInput } from '@/components/ui/NumberInput'

const inputClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text outline-none transition-colors'
const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

interface FieldDef {
  key: string
  label: string
  type: 'number' | 'select' | 'text' | 'boolean'
  unit?: string
  placeholder?: string
  default: number | string | boolean
  step?: number
  min?: number
  max?: number
  options?: string[]
  penceDisplay?: boolean
}

const WORKER_FIELDS: Record<string, FieldDef[]> = {
  reconciliation: [
    { key: 'amount_tolerance_minor_units', type: 'number',  label: 'Amount tolerance',          penceDisplay: true, default: 150 },
    { key: 'amount_tolerance_pct',         type: 'number',  label: 'Amount tolerance %',        unit: '0–0.01', step: 0.0001, min: 0, max: 0.01, default: 0.0003 },
    { key: 'date_tolerance_days',          type: 'number',  label: 'Date tolerance',            unit: 'days', default: 5 },
    { key: 'reconciliation_frequency',     type: 'select',  label: 'Run frequency',             options: ['daily', 'weekly', 'real_time'], default: 'daily' },
    { key: 'unmatched_alert_days',         type: 'number',  label: 'Alert on unmatched after',  unit: 'days', default: 5 },
    { key: 'stale_open_item_days',         type: 'number',  label: 'Stale open item threshold', unit: 'days', default: 90 },
    { key: 'auto_match_confidence_min',    type: 'number',  label: 'Auto-match min confidence', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.95 },
  ],
  document_intelligence: [
    { key: 'auto_approve_threshold',            type: 'number',  label: 'Auto-approve under',            penceDisplay: true, default: 50000 },
    { key: 'po_match_required',                 type: 'boolean', label: 'PO match required',             default: true },
    { key: 'po_tolerance_pct',                  type: 'number',  label: 'PO tolerance',                  unit: '0–0.10', step: 0.01, min: 0, max: 0.1, default: 0.03 },
    { key: 'duplicate_window_days',             type: 'number',  label: 'Duplicate window',              unit: 'days', default: 90 },
    { key: 'max_invoice_age_days',              type: 'number',  label: 'Max invoice age',               unit: 'days', default: 180 },
    { key: 'new_vendor_flag_enabled',           type: 'boolean', label: 'Flag new vendors',              default: true },
    { key: 'approval_tier_1_limit',             type: 'number',  label: 'Approval tier 1 limit',         penceDisplay: true, default: 100000 },
    { key: 'approval_tier_2_limit',             type: 'number',  label: 'Approval tier 2 limit',         penceDisplay: true, default: 1000000 },
    { key: 'receipt_required_above',            type: 'number',  label: 'Receipt required above',        penceDisplay: true, default: 2500 },
    { key: 'submission_deadline_days',          type: 'number',  label: 'Submission deadline',           unit: 'days', default: 30 },
    { key: 'ocr_confidence_min',                type: 'number',  label: 'OCR min confidence',            unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.82 },
    { key: 'duplicate_receipt_window_days',     type: 'number',  label: 'Duplicate receipt window',      unit: 'days', default: 365 },
    { key: 'auto_approve_receipt_below',        type: 'number',  label: 'Auto-approve receipt below',    penceDisplay: true, default: 1000 },
    { key: 'contract_extraction_enabled',       type: 'boolean', label: 'Contract extraction enabled',   default: true },
  ],
  ai_accountant: [
    { key: 'auto_categorise_confidence_min', type: 'number',  label: 'Auto-categorise min confidence', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.90 },
    { key: 'human_review_confidence_min',    type: 'number',  label: 'Human review below confidence',  unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.70 },
    { key: 'learn_from_corrections',         type: 'boolean', label: 'Learn from corrections',         default: true },
    { key: 'strict_coa_mode',                type: 'boolean', label: 'Strict COA mode',                default: true },
    { key: 'bulk_categorise_batch_size',     type: 'number',  label: 'Batch size',                     unit: 'transactions', default: 500 },
    { key: 'model_retrain_frequency_days',   type: 'number',  label: 'Model retrain frequency',        unit: 'days', default: 30 },
    { key: 'close_run_day_of_month',         type: 'number',  label: 'Month-end close run day',        unit: 'day of month', min: 1, max: 28, default: 1 },
    { key: 'payroll_reconcile_enabled',      type: 'boolean', label: 'Payroll reconciliation enabled', default: true },
  ],
  spend_control: [
    { key: 'auto_approve_threshold',       type: 'number',  label: 'Auto-approve bills under',    penceDisplay: true, default: 50000 },
    { key: 'duplicate_window_days',        type: 'number',  label: 'Duplicate window',            unit: 'days', default: 30 },
    { key: 'per_transaction_limit',        type: 'number',  label: 'Per-transaction limit',       penceDisplay: true, default: 50000 },
    { key: 'daily_spend_limit',            type: 'number',  label: 'Daily spend limit',           penceDisplay: true, default: 200000 },
    { key: 'monthly_spend_limit',          type: 'number',  label: 'Monthly spend limit',         penceDisplay: true, default: 500000 },
    { key: 'receipt_required_above',       type: 'number',  label: 'Receipt required above',      penceDisplay: true, default: 2500 },
    { key: 'pre_approval_required_above',  type: 'number',  label: 'Pre-approval required above', penceDisplay: true, default: 100000 },
    { key: 'cash_advance_enabled',         type: 'boolean', label: 'Cash advances enabled',       default: false },
    { key: 'meals_per_diem_limit',         type: 'number',  label: 'Meals per diem limit',        penceDisplay: true, default: 10000 },
    { key: 'hotel_daily_rate_limit',       type: 'number',  label: 'Hotel daily rate limit',      penceDisplay: true, default: 35000 },
  ],
  ar_collections: [
    { key: 'reminder_1_days_overdue',         type: 'number',  label: 'First reminder after',         unit: 'days overdue', default: 3 },
    { key: 'reminder_2_days_overdue',         type: 'number',  label: 'Second reminder after',        unit: 'days overdue', default: 14 },
    { key: 'escalate_days',                   type: 'number',  label: 'Escalate after',               unit: 'days overdue', default: 45 },
    { key: 'legal_referral_days_overdue',     type: 'number',  label: 'Legal referral after',         unit: 'days overdue', default: 90 },
    { key: 'max_calls_per_debt_per_week',     type: 'number',  label: 'Max calls per debt per week',  unit: 'calls/week (max 7)', min: 1, max: 7, default: 7 },
    { key: 'late_fee_enabled',                type: 'boolean', label: 'Late fee enabled',             default: true },
    { key: 'late_fee_fixed_amount',           type: 'number',  label: 'Late fee amount',              penceDisplay: true, default: 4000 },
    { key: 'minimum_balance_for_collections', type: 'number',  label: 'Min balance for collections',  penceDisplay: true, default: 5000 },
    { key: 'write_off_block_threshold',       type: 'number',  label: 'Write-off block threshold',    penceDisplay: true, default: 50000 },
  ],
  risk_compliance: [
    { key: 'risk_score_block',                    type: 'number',  label: 'Block above risk score',            unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.85 },
    { key: 'review_score_threshold',              type: 'number',  label: 'Review above risk score',           unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.65 },
    { key: 'velocity_window_minutes',             type: 'number',  label: 'Velocity window',                   unit: 'minutes', default: 60 },
    { key: 'velocity_max_txns',                   type: 'number',  label: 'Max transactions per window',       unit: 'count', default: 10 },
    { key: 'single_transaction_max',              type: 'number',  label: 'Single transaction max',            penceDisplay: true, default: 1000000 },
    { key: 'new_merchant_risk_boost',             type: 'number',  label: 'New merchant risk boost',           unit: '0–0.30', step: 0.01, min: 0, max: 0.3, default: 0.15 },
    { key: 'unusual_hours_risk_boost',            type: 'number',  label: 'Unusual hours risk boost',          unit: '0–0.25', step: 0.01, min: 0, max: 0.25, default: 0.10 },
    { key: 'model_retrain_frequency_days',        type: 'number',  label: 'Model retrain frequency',           unit: 'days', default: 14 },
    { key: 'ctr_threshold',                       type: 'number',  label: 'CTR threshold',                     penceDisplay: true, default: 1000000 },
    { key: 'structuring_window_hours',            type: 'number',  label: 'Structuring detection window',      unit: 'hours', default: 24 },
    { key: 'structuring_cumulative_threshold',    type: 'number',  label: 'Structuring cumulative threshold',  penceDisplay: true, default: 900000 },
    { key: 'sar_auto_file_enabled',               type: 'boolean', label: 'SAR auto-file enabled',             default: false },
    { key: 'kyc_refresh_standard_days',           type: 'number',  label: 'KYC refresh (standard)',            unit: 'days', default: 1825 },
    { key: 'kyc_refresh_high_risk_days',          type: 'number',  label: 'KYC refresh (high risk)',           unit: 'days', default: 365 },
    { key: 'gdpr_data_retention_days',            type: 'number',  label: 'GDPR data retention',               unit: 'days', default: 2555 },
    { key: 'pep_screening_enabled',               type: 'boolean', label: 'PEP screening enabled',             default: true },
    { key: 'frameworks',                          type: 'text',    label: 'Regulatory frameworks',             placeholder: 'AML, KYC, GDPR', default: 'AML, KYC' },
  ],
  treasury_cash: [
    { key: 'minimum_operating_balance_alert_days', type: 'number',  label: 'Min operating balance alert', unit: 'days of expenses', default: 45 },
    { key: 'runway_alert_days',                    type: 'number',  label: 'Runway alert threshold',      unit: 'days', default: 90 },
    { key: 'forecast_horizon_days',                type: 'number',  label: 'Forecast horizon',            unit: 'days', default: 91 },
    { key: 'forecast_update_frequency',            type: 'select',  label: 'Forecast update frequency',   options: ['daily', 'weekly', 'monthly'], default: 'weekly' },
    { key: 'cash_sweep_enabled',                   type: 'boolean', label: 'Cash sweep enabled',          default: false },
    { key: 'bank_counterparty_limit',              type: 'number',  label: 'Bank counterparty limit',     penceDisplay: true, default: 25000000 },
    { key: 'bank_counterparty_count_min',          type: 'number',  label: 'Min bank counterparties',     unit: 'banks', default: 2 },
    { key: 'payroll_reserve_days',                 type: 'number',  label: 'Payroll reserve',             unit: 'days', default: 5 },
    { key: 'fx_monitoring_enabled',                type: 'boolean', label: 'FX exposure monitoring',      default: true },
    { key: 'budget_variance_alert_pct',            type: 'number',  label: 'Budget variance alert',       unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.10 },
  ],
  revenue_recognition: [
    { key: 'accounting_standard',                      type: 'select',  label: 'Accounting standard',              options: ['ASC 606', 'IFRS 15'], default: 'ASC 606' },
    { key: 'recognition_method',                       type: 'select',  label: 'Default recognition method',       options: ['at-point', 'over-time'], default: 'at-point' },
    { key: 'recognition_frequency',                    type: 'select',  label: 'Recognition frequency',            options: ['daily', 'monthly'], default: 'daily' },
    { key: 'variable_consideration_method',            type: 'select',  label: 'Variable consideration method',    options: ['expected_value', 'most_likely_amount'], default: 'expected_value' },
    { key: 'variable_consideration_constraint_enabled',type: 'boolean', label: 'Variable consideration constraint',default: true },
    { key: 'period_lock_enforcement',                  type: 'boolean', label: 'Period lock enforcement',          default: true },
  ],
  credit_underwriting: [
    { key: 'min_credit_score',           type: 'number',  label: 'Minimum credit score',       unit: 'score', default: 620 },
    { key: 'max_dti_ratio',              type: 'number',  label: 'Max debt-to-income ratio',   unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.43 },
    { key: 'auto_approve_score_min',     type: 'number',  label: 'Auto-approve score min',     unit: 'score', default: 720 },
    { key: 'max_ltv_ratio',              type: 'number',  label: 'Max LTV ratio',              unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.80 },
    { key: 'min_employment_months',      type: 'number',  label: 'Min employment duration',    unit: 'months', default: 6 },
    { key: 'max_loan_amount',            type: 'number',  label: 'Max loan amount',            penceDisplay: true, default: 50000000 },
    { key: 'adverse_action_notice_auto', type: 'boolean', label: 'Auto adverse action notice', default: true },
  ],
}

export function getDefaultConfig(toolType: string): Record<string, unknown> {
  return Object.fromEntries((WORKER_FIELDS[toolType] ?? []).map(f => [f.key, f.default]))
}

interface ToolConfigFieldsProps {
  toolType: string
  config: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

export function ToolConfigFields({ toolType, config, onChange }: ToolConfigFieldsProps) {
  const fields = WORKER_FIELDS[toolType] ?? []
  if (fields.length === 0) return null

  return (
    <div className="space-y-3 border-t border-brand-border pt-3">
      <p className={labelClass}>Tool Settings</p>
      {fields.map((field) => {
        const value = config[field.key] ?? field.default

        if (field.type === 'boolean') {
          const isOn = value as boolean
          return (
            <div key={field.key} className="flex items-center justify-between">
              <span className={labelClass}>{field.label}</span>
              <button
                type="button"
                onClick={() => onChange(field.key, !isOn)}
                className={`text-xs font-mono px-3 py-1 rounded-sm border transition-colors ${isOn ? 'border-brand-green text-brand-green' : 'border-brand-border text-brand-muted'}`}
              >
                {isOn ? 'ON' : 'OFF'}
              </button>
            </div>
          )
        }

        if (field.type === 'select') {
          return (
            <div key={field.key} className="space-y-1.5">
              <label className={labelClass}>{field.label}</label>
              <Select
                value={value as string}
                onChange={v => onChange(field.key, v)}
                options={field.options!.map(opt => ({ value: opt, label: opt }))}
              />
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
            <label className={labelClass}>{field.label}{field.unit && <span className="normal-case opacity-60"> ({field.unit})</span>}</label>
            <NumberInput
              value={value as number}
              min={field.min ?? 0}
              max={field.max}
              step={field.step ?? 1}
              onChange={v => onChange(field.key, v)}
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
