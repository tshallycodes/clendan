'use client'

import { useState } from 'react'
import { Info } from '@phosphor-icons/react'
import { Select } from '@/components/ui/Select'
import { NumberInput } from '@/components/ui/NumberInput'
import { useCurrency } from '@/components/Providers'
import { CURRENCY_MAP } from '@/lib/currency'

const inputClass = 'w-full bg-brand-bg border border-brand-border focus:border-brand-green rounded-sm px-3 py-2 text-xs font-mono text-brand-text outline-none transition-colors'
const labelClass = 'text-[10px] font-mono text-brand-muted uppercase tracking-widest'

interface FieldDef {
  key: string
  label: string
  type: 'number' | 'select' | 'text' | 'boolean' | 'multiselect'
  description?: string
  unit?: string
  placeholder?: string
  default: number | string | boolean | string[]
  step?: number
  min?: number
  max?: number
  options?: string[]
  penceDisplay?: boolean
  showWhen?: (config: Record<string, unknown>) => boolean
}

const WORKER_FIELDS: Record<string, FieldDef[]> = {
  reconciliation: [
    { key: 'amount_tolerance_minor_units', type: 'number', label: 'Amount tolerance', penceDisplay: true, default: 150,
      description: 'Max pence difference between a bank transaction and an invoice for them to count as a match. E.g. £1.50 covers minor bank charges or rounding.' },
    { key: 'amount_tolerance_pct', type: 'number', label: 'Amount tolerance %', unit: '0–0.01', step: 0.0001, min: 0, max: 0.01, default: 0.0003,
      description: 'Percentage difference allowed on top of the fixed pence tolerance. Useful for invoices with variable fees. 0.0003 = 0.03%.' },
    { key: 'date_tolerance_days', type: 'number', label: 'Date tolerance', unit: 'days', default: 5,
      description: 'How many days apart a bank transaction and an invoice date can be and still match. E.g. 5 days covers end-of-month timing differences.' },
    { key: 'reconciliation_frequency', type: 'select', label: 'Run frequency', options: ['daily', 'weekly', 'real-time'], default: 'daily',
      description: 'How often the reconciliation runs automatically. Daily processes overnight. Real-time triggers on each new bank transaction.' },
    { key: 'run_hour_utc', type: 'number', label: 'Run at hour', unit: '0–23', min: 0, max: 23, default: 2,
      description: 'Hour of the day (in your organisation timezone set in Settings) to fire daily or weekly reconciliation. 0 = midnight, 9 = 9:00 AM. Has no effect for Real-time frequency.' },
    { key: 'run_day_of_week', type: 'select', label: 'Weekly run day', options: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'], default: 'monday',
      description: 'Which day of the week to run reconciliation.',
      showWhen: (cfg) => cfg['reconciliation_frequency'] === 'weekly' },
    { key: 'unmatched_alert_days', type: 'number', label: 'Alert on unmatched after', unit: 'days', default: 5,
      description: 'Flag any transaction or invoice that has been unmatched for longer than this many days. Prevents items slipping through unnoticed.' },
    { key: 'stale_open_item_days', type: 'number', label: 'Stale open item threshold', unit: 'days', default: 90,
      description: 'Mark open items as stale if they remain unmatched beyond this threshold. Prompts a write-off or escalation review.' },
    { key: 'auto_match_confidence_min', type: 'number', label: 'Auto-match min confidence', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.95,
      description: "Claude must reach at least this confidence (0–1) to auto-match without human review. 0.95 means 95% certainty required before matching happens automatically." },
    { key: 'include_reconciled', type: 'boolean', label: 'Re-reconcile previously matched transactions', default: false,
      description: 'When on, transactions already marked as reconciled in a previous run are included in future runs. Use this if you suspect a prior run matched incorrectly or you want to audit completed matches.' },
  ],
  document_intelligence: [
    { key: 'accounting_integrations', type: 'multiselect', label: 'Push receipts to', default: [],
      options: ['quickbooks', 'xero', 'freshbooks'],
      description: 'When a receipt is uploaded and classified, it is automatically pushed to all selected integrations. At least one must be selected — uploads will fail with an error if none are configured.' },
  ],
  ai_accountant: [
    { key: 'auto_categorise_confidence_min', type: 'number', label: 'Auto-categorise min confidence', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.90,
      description: "Transactions where Claude's confidence is at or above this are categorised automatically into your chart of accounts." },
    { key: 'human_review_confidence_min', type: 'number', label: 'Human review below confidence', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.70,
      description: "Transactions where confidence falls between this and the auto-categorise threshold are sent for human review. Below this lower bound they're flagged for investigation." },
    { key: 'learn_from_corrections', type: 'boolean', label: 'Learn from corrections', default: true,
      description: 'When on, the model updates its categorisation based on corrections made by your team. Accuracy improves over time.' },
    { key: 'strict_coa_mode', type: 'boolean', label: 'Strict COA mode', default: true,
      description: 'When on, the tool only assigns codes that already exist in your chart of accounts. Prevents ad-hoc or uncategorised codes being created automatically.' },
    { key: 'bulk_categorise_batch_size', type: 'number', label: 'Batch size', unit: 'transactions', default: 500,
      description: 'How many transactions are processed in each batch during bulk categorisation runs. Smaller batches are slower but more predictable.' },
    { key: 'model_retrain_frequency_days', type: 'number', label: 'Model retrain frequency', unit: 'days', default: 30,
      description: 'How often the AI model retrains on your latest data and team corrections. More frequent = faster improvement.' },
    { key: 'close_run_day_of_month', type: 'number', label: 'Month-end close run day', unit: 'day of month', min: 1, max: 28, default: 1,
      description: 'The day of each month when the month-end close job runs automatically. Day 1 = the first of every month.' },
    { key: 'payroll_reconcile_enabled', type: 'boolean', label: 'Payroll reconciliation enabled', default: true,
      description: 'When on, payroll journal entries are automatically matched to bank transactions during each month-end close run.' },
  ],
  spend_control: [
    { key: 'auto_approve_threshold', type: 'number', label: 'Auto-approve bills under', penceDisplay: true, default: 50000,
      description: 'Bills and expenses under this amount are approved automatically. Above this, a human must review before payment.' },
    { key: 'duplicate_window_days', type: 'number', label: 'Duplicate window', unit: 'days', default: 30,
      description: 'Look back this many days for a duplicate bill or expense claim. Prevents paying the same bill twice.' },
    { key: 'per_transaction_limit', type: 'number', label: 'Per-transaction limit', penceDisplay: true, default: 50000,
      description: 'No single spend transaction may exceed this amount. Transactions above this are blocked outright.' },
    { key: 'daily_spend_limit', type: 'number', label: 'Daily spend limit', penceDisplay: true, default: 200000,
      description: 'Total company spend in any calendar day cannot exceed this. Helps prevent large unexpected outflows.' },
    { key: 'monthly_spend_limit', type: 'number', label: 'Monthly spend limit', penceDisplay: true, default: 500000,
      description: 'Total spend for the calendar month cannot exceed this. Acts as a monthly budget guardrail.' },
    { key: 'receipt_required_above', type: 'number', label: 'Receipt required above', penceDisplay: true, default: 2500,
      description: 'Any expense above this amount requires a receipt or supporting document to be submitted before reimbursement.' },
    { key: 'pre_approval_required_above', type: 'number', label: 'Pre-approval required above', penceDisplay: true, default: 100000,
      description: 'Purchases above this amount require approval before the purchase is made, not after. Prevents large unplanned spend.' },
    { key: 'cash_advance_enabled', type: 'boolean', label: 'Cash advances enabled', default: false,
      description: 'When on, employees can request cash advances through the platform.' },
    { key: 'meals_per_diem_limit', type: 'number', label: 'Meals per diem limit', penceDisplay: true, default: 10000,
      description: 'Maximum amount reimbursed per person per day for meals. Claims above this are reduced to the limit automatically.' },
    { key: 'hotel_daily_rate_limit', type: 'number', label: 'Hotel daily rate limit', penceDisplay: true, default: 35000,
      description: 'Maximum nightly hotel rate that will be reimbursed. Rooms booked above this require additional justification.' },
  ],
  ar_collections: [
    { key: 'reminder_1_days_overdue', type: 'number', label: 'First reminder after', unit: 'days overdue', default: 3,
      description: 'Send the first (gentle) payment reminder when an invoice is this many days past its due date.' },
    { key: 'reminder_2_days_overdue', type: 'number', label: 'Second reminder after', unit: 'days overdue', default: 14,
      description: 'Send the second (firmer) reminder when an invoice reaches this many days overdue.' },
    { key: 'escalate_days', type: 'number', label: 'Escalate after', unit: 'days overdue', default: 45,
      description: 'When a debt reaches this age, escalate to a senior contact or collections specialist for direct outreach.' },
    { key: 'legal_referral_days_overdue', type: 'number', label: 'Legal referral after', unit: 'days overdue', default: 90,
      description: 'Debts overdue by this many days are flagged for legal review or handover to an external collections agency.' },
    { key: 'max_calls_per_debt_per_week', type: 'number', label: 'Max calls per debt per week', unit: 'calls/week (max 7)', min: 1, max: 7, default: 7,
      description: 'Maximum contact attempts per debtor per week. Regulatory maximum is 7 in most jurisdictions — set lower if your compliance team requires it.' },
    { key: 'late_fee_enabled', type: 'boolean', label: 'Late fee enabled', default: true,
      description: 'When on, a fixed late fee is automatically added to invoices once they become overdue.' },
    { key: 'late_fee_fixed_amount', type: 'number', label: 'Late fee amount', penceDisplay: true, default: 4000,
      description: 'The fixed amount added as a late fee when an invoice becomes overdue. Applied once per invoice.' },
    { key: 'minimum_balance_for_collections', type: 'number', label: 'Min balance for collections', penceDisplay: true, default: 5000,
      description: 'Debts below this amount are not actively chased — the cost of collection would exceed the value of the debt.' },
    { key: 'write_off_block_threshold', type: 'number', label: 'Write-off block threshold', penceDisplay: true, default: 50000,
      description: 'Debts above this amount cannot be written off without explicit human approval — prevents accidental large write-offs.' },
  ],
  risk_compliance: [
    { key: 'risk_score_block', type: 'number', label: 'Block above risk score', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.85,
      description: 'Transactions with a risk score above this are automatically blocked. 0.85 = block the highest-risk 15% of transactions.' },
    { key: 'review_score_threshold', type: 'number', label: 'Review above risk score', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.65,
      description: 'Transactions above this score (but below the block threshold) are sent for human review rather than blocked outright.' },
    { key: 'velocity_window_minutes', type: 'number', label: 'Velocity window', unit: 'minutes', default: 60,
      description: 'The time window used to detect unusually high transaction frequency from the same source. E.g. 60 mins = look at the last hour.' },
    { key: 'velocity_max_txns', type: 'number', label: 'Max transactions per window', unit: 'count', default: 10,
      description: 'Maximum number of transactions from the same source allowed within the velocity window before a flag is raised.' },
    { key: 'single_transaction_max', type: 'number', label: 'Single transaction max', penceDisplay: true, default: 1000000,
      description: 'Any single transaction above this amount is automatically blocked, regardless of risk score.' },
    { key: 'new_merchant_risk_boost', type: 'number', label: 'New merchant risk boost', unit: '0–0.30', step: 0.01, min: 0, max: 0.3, default: 0.15,
      description: 'How much the base risk score increases when a transaction goes to a merchant never seen before. 0.15 = +15 percentage points added to the score.' },
    { key: 'unusual_hours_risk_boost', type: 'number', label: 'Unusual hours risk boost', unit: '0–0.25', step: 0.01, min: 0, max: 0.25, default: 0.10,
      description: 'How much the risk score increases for transactions made outside normal business hours (typically 22:00–06:00).' },
    { key: 'model_retrain_frequency_days', type: 'number', label: 'Model retrain frequency', unit: 'days', default: 14,
      description: 'How often the fraud detection model retrains on new transaction data. Default is every 14 days.' },
    { key: 'ctr_threshold', type: 'number', label: 'CTR threshold', penceDisplay: true, default: 1000000,
      description: 'Currency Transaction Report threshold — transactions above this must be reported to the relevant regulator. Default is the standard £10,000 legal minimum.' },
    { key: 'structuring_window_hours', type: 'number', label: 'Structuring detection window', unit: 'hours', default: 24,
      description: 'Time window for detecting structuring — where a large payment is split into smaller ones to avoid reporting thresholds.' },
    { key: 'structuring_cumulative_threshold', type: 'number', label: 'Structuring cumulative threshold', penceDisplay: true, default: 900000,
      description: 'If multiple transactions within the structuring window total above this amount, the pattern is flagged as potential structuring.' },
    { key: 'sar_auto_file_enabled', type: 'boolean', label: 'SAR auto-file enabled', default: false,
      description: 'When on, Suspicious Activity Reports are filed automatically without human review. Off by default — most organisations prefer manual sign-off before filing.' },
    { key: 'kyc_refresh_standard_days', type: 'number', label: 'KYC refresh (standard)', unit: 'days', default: 1825,
      description: 'How often standard-risk customers must be re-verified. Default is 1,825 days (5 years).' },
    { key: 'kyc_refresh_high_risk_days', type: 'number', label: 'KYC refresh (high risk)', unit: 'days', default: 365,
      description: 'How often high-risk customers must be re-verified. Default is 365 days (annually).' },
    { key: 'gdpr_data_retention_days', type: 'number', label: 'GDPR data retention', unit: 'days', default: 2555,
      description: 'How many days personal data is retained before automatic deletion. Default is 2,555 days (7 years) — the standard financial regulatory retention period.' },
    { key: 'pep_screening_enabled', type: 'boolean', label: 'PEP screening enabled', default: true,
      description: 'When on, counterparties are screened against Politically Exposed Persons lists on every transaction.' },
    { key: 'frameworks', type: 'text', label: 'Regulatory frameworks', placeholder: 'AML, KYC, GDPR', default: 'AML, KYC',
      description: 'Comma-separated list of regulatory frameworks the compliance tool enforces. Determines which rules and checks are applied (e.g. AML, KYC, GDPR).' },
  ],
  treasury_cash: [
    { key: 'minimum_operating_balance_alert_days', type: 'number', label: 'Min operating balance alert', unit: 'days of expenses', default: 45,
      description: 'Alert when cash reserves fall below this many days of average operating expenses. E.g. 45 = alert if less than 45 days of runway in the bank.' },
    { key: 'runway_alert_days', type: 'number', label: 'Runway alert threshold', unit: 'days', default: 90,
      description: "Alert when the company's total cash runway drops below this many days. Runway = total cash divided by monthly burn rate." },
    { key: 'forecast_horizon_days', type: 'number', label: 'Forecast horizon', unit: 'days', default: 91,
      description: 'How many days ahead the cash flow forecast projects. 91 days = one quarter of forward visibility.' },
    { key: 'forecast_update_frequency', type: 'select', label: 'Forecast update frequency', options: ['daily', 'weekly', 'monthly'], default: 'weekly',
      description: 'How often the cash forecast refreshes with new actuals and incoming payment data.' },
    { key: 'cash_sweep_enabled', type: 'boolean', label: 'Cash sweep enabled', default: false,
      description: 'When on, idle cash above your minimum operating balance is automatically swept to higher-yield accounts overnight.' },
    { key: 'bank_counterparty_limit', type: 'number', label: 'Bank counterparty limit', penceDisplay: true, default: 25000000,
      description: 'Maximum cash held at any single bank. Protects against bank failure risk — FSCS covers only £85,000 per institution per person.' },
    { key: 'bank_counterparty_count_min', type: 'number', label: 'Min bank counterparties', unit: 'banks', default: 2,
      description: 'Minimum number of separate banking relationships required. Enforces your cash diversification policy.' },
    { key: 'payroll_reserve_days', type: 'number', label: 'Payroll reserve', unit: 'days', default: 5,
      description: 'A cash reserve covering at least this many days of payroll must always be maintained. Prevents payroll being disrupted by a short-term cash shortfall.' },
    { key: 'fx_monitoring_enabled', type: 'boolean', label: 'FX exposure monitoring', default: true,
      description: 'When on, foreign currency balances and exposures are monitored and flagged when they exceed risk thresholds.' },
    { key: 'budget_variance_alert_pct', type: 'number', label: 'Budget variance alert', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.10,
      description: 'Alert when any budget line is tracking more than this percentage over or under target. 0.10 = alert at 10% variance.' },
  ],
  revenue_recognition: [
    { key: 'accounting_standard', type: 'select', label: 'Accounting standard', options: ['ASC 606', 'IFRS 15'], default: 'ASC 606',
      description: 'Which revenue accounting standard applies to your business — ASC 606 (US GAAP) or IFRS 15 (international).' },
    { key: 'recognition_method', type: 'select', label: 'Default recognition method', options: ['at-point', 'over-time'], default: 'at-point',
      description: "Default method for recognising revenue. 'At point' for one-off sales delivered instantly; 'over time' for subscriptions and multi-period contracts." },
    { key: 'recognition_frequency', type: 'select', label: 'Recognition frequency', options: ['daily', 'monthly'], default: 'daily',
      description: 'How often recognition journal entries are posted. Daily suits SaaS and subscriptions; monthly suits other business models.' },
    { key: 'variable_consideration_method', type: 'select', label: 'Variable consideration method', options: ['expected_value', 'most_likely_amount'], default: 'expected_value',
      description: 'How to estimate variable revenue (discounts, bonuses, refunds). Expected value weights all probability-weighted outcomes; most likely picks the single most probable amount.' },
    { key: 'variable_consideration_constraint_enabled', type: 'boolean', label: 'Variable consideration constraint', default: true,
      description: 'When on, applies the constraint rule from ASC 606 / IFRS 15 — prevents recognising revenue that is highly likely to reverse in a future period.' },
    { key: 'period_lock_enforcement', type: 'boolean', label: 'Period lock enforcement', default: true,
      description: 'When on, closed accounting periods are locked and cannot be modified. Prevents revenue being backdated or manipulated after close.' },
  ],
  credit_underwriting: [
    { key: 'min_credit_score', type: 'number', label: 'Minimum credit score', unit: 'score', default: 620,
      description: 'Applicants with a credit score below this are automatically declined. 620 is a common minimum for standard credit products.' },
    { key: 'max_dti_ratio', type: 'number', label: 'Max debt-to-income ratio', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.43,
      description: 'Maximum debt-to-income ratio (monthly debt payments divided by gross monthly income). Applications above this are automatically declined.' },
    { key: 'auto_approve_score_min', type: 'number', label: 'Auto-approve score min', unit: 'score', default: 720,
      description: 'Applications with a credit score at or above this are automatically approved without manual underwriter review.' },
    { key: 'max_ltv_ratio', type: 'number', label: 'Max LTV ratio', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.80,
      description: 'Maximum loan-to-value ratio for secured lending. 0.80 means the loan cannot exceed 80% of the asset or property value.' },
    { key: 'min_employment_months', type: 'number', label: 'Min employment duration', unit: 'months', default: 6,
      description: 'Applicants must have been continuously employed for at least this many months to qualify for credit.' },
    { key: 'max_loan_amount', type: 'number', label: 'Max loan amount', penceDisplay: true, default: 50000000,
      description: 'The maximum loan amount the tool will approve automatically. Amounts above this require manual underwriting.' },
    { key: 'adverse_action_notice_auto', type: 'boolean', label: 'Auto adverse action notice', default: true,
      description: 'When on, rejection notices are automatically sent to declined applicants. This is legally required in most jurisdictions.' },
  ],
  tax_compliance: [
    { key: 'vat_alert_threshold_cents', type: 'number', label: 'VAT liability alert threshold', penceDisplay: true, default: 1000000,
      description: 'Alert and route for approval when the net VAT liability for the period exceeds this amount. Default £10,000.' },
    { key: 'missing_tax_flag_threshold_cents', type: 'number', label: 'Missing tax code flag above', penceDisplay: true, default: 10000,
      description: 'Flag any invoice, bill, or expense above this amount that has no tax code assigned. Default £100 — keeps low-value items out of the review queue.' },
  ],
  financial_reporting: [
    { key: 'lookback_days', type: 'number', label: 'Reporting lookback period', unit: 'days', default: 30,
      description: 'How many days back the report covers when run. E.g. 30 = last 30 days of P&L, balance sheet, and cash flow.' },
    { key: 'anomaly_variance_pct', type: 'number', label: 'Anomaly variance threshold', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.25,
      description: 'Flag a line item as anomalous if it varies by more than this percentage versus the prior equivalent period. 0.25 = flag anything more than 25% different.' },
  ],
  payment_run: [
    { key: 'auto_pay_limit_cents', type: 'number', label: 'Auto-pay limit', penceDisplay: true, default: 100000,
      description: 'Bills up to this amount are automatically scheduled for payment without a human approver. Default £1,000.' },
    { key: 'approval_threshold_cents', type: 'number', label: 'Approval required above', penceDisplay: true, default: 250000,
      description: 'Bills above this amount are routed to a human approver before being added to the payment run. Default £2,500.' },
    { key: 'due_within_days', type: 'number', label: 'Pay bills due within', unit: 'days', default: 7,
      description: 'Only include bills in the payment run that are due within this many days. Prevents paying too far in advance and helps manage cash timing.' },
    { key: 'max_bills_per_run', type: 'number', label: 'Max bills per run', unit: 'bills', default: 50,
      description: 'Maximum number of bills included in a single payment run batch. Limits the size of any one run for easier review.' },
  ],
  budgeting: [
    { key: 'over_budget_alert_pct', type: 'number', label: 'Over-budget alert threshold', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.10,
      description: 'Alert when actual spend on a budget line exceeds the budgeted amount by more than this percentage. 0.10 = alert at 10% overspend.' },
    { key: 'critical_overspend_pct', type: 'number', label: 'Critical overspend threshold', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.25,
      description: 'Route for human approval when actual spend exceeds the budget line by more than this percentage. 0.25 = escalate at 25% over budget.' },
  ],
}

export function getDefaultConfig(toolType: string): Record<string, unknown> {
  return Object.fromEntries((WORKER_FIELDS[toolType] ?? []).map(f => [f.key, f.default]))
}

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
                  className={`shrink-0 text-xs font-mono px-3 py-1 rounded-sm border transition-colors ${isOn ? 'border-brand-green text-brand-green' : 'border-brand-border text-brand-muted'}`}
                >
                  {isOn ? 'ON' : 'OFF'}
                </button>
              </div>
              {hintOpen && field.description && (
                <p className="mt-1.5 text-[10px] font-mono text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
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
                <p className="text-[10px] font-mono text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
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
                <p className="text-[10px] font-mono text-brand-muted bg-brand-bg border border-brand-border rounded-sm px-3 py-2">
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
                      <span className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center shrink-0 transition-colors ${
                        isChecked ? 'bg-[#00C853] border-[#00C853]' : 'bg-brand-bg border-brand-border'
                      }`}>
                        {isChecked && (
                          <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                            <path d="M1 3L3 5L7 1" stroke="black" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </span>
                      <span className="text-[11px] font-mono text-brand-text">
                        {opt.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </span>
                    </button>
                  )
                })}
              </div>
              )}
              {hintOpen && field.description && (
                <p className="text-[10px] font-mono text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
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
                <p className="text-[10px] font-mono text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
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
              <p className="text-[10px] font-mono text-brand-muted">{currencySymbol}{((value as number) / 100).toFixed(2)}</p>
            )}
            {hintOpen && field.description && (
              <p className="text-[10px] font-mono text-brand-secondary bg-brand-elevated border border-brand-border rounded-sm px-2.5 py-2 leading-relaxed">
                {field.description}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
