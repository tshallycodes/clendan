export interface FieldDef {
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

export const TOOL_FIELDS: Record<string, FieldDef[]> = {
  document_intelligence: [
    { key: 'auto_threshold_minor', type: 'number', label: 'Auto-approve invoices under', penceDisplay: true, default: 50000,
      description: 'Invoices below this total are auto-approved and the bill is written to your connected ERP. Default £500.' },
    { key: 'block_threshold_minor', type: 'number', label: 'Block invoices over', penceDisplay: true, default: 1000000,
      description: 'Invoices above this total are blocked outright and never auto-processed. Default £10,000.' },
    { key: 'min_ocr_confidence', type: 'number', label: 'Minimum extraction confidence', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.85,
      description: 'Invoices extracted below this confidence are routed to Approvals for manual review instead of auto-approved.' },
    { key: 'duplicate_window_days', type: 'number', label: 'Duplicate detection window', unit: 'days', default: 90,
      description: 'Flag an invoice as a duplicate if the same invoice number was already seen within this many days.' },
  ],
  reconciliation: [
    // ── Bank ──────────────────────────────────────────────────────────────
    { key: 'amount_tolerance_minor_units', type: 'number', label: 'Bank · Amount tolerance', penceDisplay: true, default: 150,
      description: 'Max difference in minor currency units (pence, cents) between a bank transaction and invoice amount for them to count as a match. The amount shown below reflects your set currency.' },
    { key: 'date_tolerance_days', type: 'number', label: 'Bank · Date tolerance', unit: 'days', default: 5,
      description: 'How many days apart a bank transaction and an invoice date can be and still match. 5 days covers typical end-of-month timing differences.' },
    { key: 'unmatched_alert_days', type: 'number', label: 'Bank · Alert on unmatched after', unit: 'days', default: 5,
      description: 'Flag any bank transaction that has been unmatched for longer than this many days. Prevents items slipping through unnoticed.' },
    { key: 'stale_open_item_days', type: 'number', label: 'Bank · Stale open item threshold', unit: 'days', default: 90,
      description: 'Mark open items as stale if they remain unmatched beyond this threshold. Prompts a write-off or escalation review.' },
    { key: 'unmatched_pct_threshold', type: 'number', label: 'Bank · Unmatched % breach threshold', unit: '%', step: 1, min: 0, max: 100, default: 20,
      description: 'If more than this percentage of transactions remain unmatched after reconciliation, the run is flagged. 20 = flag when more than 20% are unmatched.' },
    { key: 'include_reconciled', type: 'boolean', label: 'Bank · Re-reconcile already matched transactions', default: false,
      description: 'When on, transactions already matched in a previous run are re-checked. Use this to audit or correct prior runs.' },
    // ── Schedule ──────────────────────────────────────────────────────────
    { key: 'reconciliation_frequency', type: 'select', label: 'Schedule · Run frequency', options: ['daily', 'weekly', 'real-time'], default: 'daily',
      description: 'How often bank reconciliation runs automatically. Daily = overnight batch. Real-time = triggers on each new bank transaction.' },
    { key: 'run_hour', type: 'number', label: 'Schedule · Run at hour', unit: '0–23', min: 0, max: 23, default: 2,
      description: 'Hour of the day (in your organisation timezone from Settings) to fire the daily or weekly run. 0 = midnight, 9 = 9:00 AM. No effect when set to Real-time.' },
    { key: 'run_day_of_week', type: 'select', label: 'Schedule · Weekly run day', options: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'], default: 'monday',
      description: 'Which day of the week to run reconciliation. Only applies when frequency is set to Weekly.',
      showWhen: (cfg) => cfg['reconciliation_frequency'] === 'weekly' },
    // ── Invoice ───────────────────────────────────────────────────────────
    { key: 'invoice_overdue_grace_days', type: 'number', label: 'Invoice · Overdue grace period', unit: 'days', default: 0,
      description: 'Number of days past the due date before an invoice is flagged as overdue. 0 = flag immediately on the due date. 7 = allow a one-week grace period before raising an alert.' },
    // ── VAT ───────────────────────────────────────────────────────────────
    { key: 'expected_vat_rate_pct', type: 'number', label: 'VAT · Expected VAT rate', unit: '%', step: 0.1, min: 0, max: 100, default: 20,
      description: 'The standard VAT rate you expect on taxable invoices. Invoices where the effective rate (tax ÷ subtotal × 100) differs by more than 1% are flagged for review. UK standard rate is 20%.' },
    // ── Payroll ───────────────────────────────────────────────────────────
    { key: 'payroll_keywords', type: 'text', label: 'Payroll · Transaction keywords', placeholder: 'payroll, salary, wages, bacs', default: 'payroll, salary, wages',
      description: 'Comma-separated keywords used to identify payroll bank transactions. Any bank payment whose description contains one of these words is included in payroll reconciliation.' },
    { key: 'payroll_salary_tolerance_pct', type: 'number', label: 'Payroll · Salary discrepancy tolerance', unit: '%', step: 0.1, min: 0, max: 20, default: 1,
      description: 'Maximum % difference between the expected salary in your roster and the actual bank payment before it is flagged as a discrepancy. 1% covers minor deductions or rounding.' },
  ],
  spend_control: [
    { key: 'accounting_sources', type: 'multiselect', label: 'Accounting sources', options: [], default: [],
      description: 'Restrict spend review to specific connected accounting integrations. Leave all unchecked to include every connected source.' },
    { key: 'auto_approve_limit_cents', type: 'number', label: 'Auto-approve under', penceDisplay: true, default: 10000,
      description: 'Expenses under this amount can be approved automatically. The agent never auto-approves anything at or above this - it is the hard ceiling for hands-off approval.' },
    { key: 'approval_required_cents', type: 'number', label: 'Approval required above', penceDisplay: true, default: 50000,
      description: 'Unapproved expenses above this amount are flagged and routed to the Approvals queue before payment.' },
    { key: 'single_expense_limit_cents', type: 'number', label: 'Single-expense hard limit', penceDisplay: true, default: 100000,
      description: 'No single expense may exceed this. Anything above is blocked outright, regardless of approval status.' },
    { key: 'receipt_required_above', type: 'number', label: 'Receipt required above', penceDisplay: true, default: 2500,
      description: 'Expenses above this amount require a receipt or supporting document before reimbursement.' },
    { key: 'monthly_limit_per_employee', type: 'number', label: 'Monthly limit per employee', penceDisplay: true, default: 500000,
      description: 'Per-employee spend budget for a calendar month. Used as a guardrail when assessing spend velocity and burn rate.' },
    { key: 'lookback_days', type: 'number', label: 'Recent review window', unit: 'days', min: 1, default: 30,
      description: 'Recent expenses within this many days are re-checked on every run (also drives the burn-rate calculation). Older expenses are only picked up if still unassessed - see the catch-up limit below.' },
    { key: 'expense_lookback_days', type: 'number', label: 'Unassessed catch-up limit', unit: 'days · 0 = no limit', min: 0, default: 0,
      description: 'How far back to catch up expenses that have never been assessed. 0 = no limit (assess every unassessed expense, any age). Set a number to ignore unassessed expenses older than that. Outstanding bills are always assessed regardless of age.' },
  ],
  tax_compliance: [
    { key: 'accounting_sources', type: 'multiselect', label: 'Accounting sources', options: [], default: [],
      description: 'Restrict VAT and tax-code analysis to specific connected accounting integrations. Leave all unchecked to include every connected source.' },
    { key: 'vat_alert_threshold_cents', type: 'number', label: 'VAT liability alert threshold', penceDisplay: true, default: 1000000,
      description: 'Alert and route for approval when the net VAT liability for the period exceeds this amount. Default £10,000.' },
    { key: 'missing_tax_flag_threshold_cents', type: 'number', label: 'Missing tax code flag above', penceDisplay: true, default: 10000,
      description: 'Flag any invoice, bill, or expense above this amount that has no tax code assigned. Default £100 - keeps low-value items out of the review queue.' },
    { key: 'lookback_days', type: 'number', label: 'Reporting lookback period', unit: 'days', min: 1, default: 90,
      description: 'How far back the VAT position is computed. Also sets the filing period label: <=31 days = monthly, <=92 = quarterly, otherwise annual. Default 90 (a quarter).' },
    { key: 'run_day_of_month', type: 'number', label: 'Schedule · Run day of month', unit: '1–28', min: 1, max: 28, default: 1,
      description: 'Day of the month the VAT position auto-recomputes and the return is recorded, in your organisation timezone (Settings). Capped at 28 so it fires every month.' },
    { key: 'run_hour', type: 'number', label: 'Schedule · Run at hour', unit: '0–23', min: 0, max: 23, default: 2,
      description: 'Hour of day the scheduled run fires, in your organisation timezone (Settings).' },
  ],
  financial_reporting: [
    { key: 'accounting_sources', type: 'multiselect', label: 'Accounting sources', options: [], default: [],
      description: 'Restrict P&L, balance-sheet, and cash-flow data to specific connected accounting integrations. Leave all unchecked to include every connected source.' },
    { key: 'bank_sources', type: 'multiselect', label: 'Bank connections', options: [], default: [],
      description: 'Which connected bank integrations to include in cash-flow and balance-sheet data. Leave all unchecked to include every connected bank.' },
    { key: 'lookback_days', type: 'number', label: 'Reporting lookback period', unit: 'days', default: 30,
      description: 'How many days back the report covers when run. E.g. 30 = last 30 days of P&L, balance sheet, and cash flow.' },
    { key: 'anomaly_variance_pct', type: 'number', label: 'Anomaly variance threshold', unit: '0–1', step: 0.01, min: 0, max: 1, default: 0.25,
      description: 'Flag a line item as anomalous if it varies by more than this percentage versus the prior equivalent period. 0.25 = flag anything more than 25% different.' },
    { key: 'run_day_of_month', type: 'number', label: 'Schedule · Run day of month', unit: '1–28', min: 1, max: 28, default: 1,
      description: 'Day of the month the report auto-generates, in your organisation timezone (Settings). Capped at 28 so it fires every month.' },
    { key: 'run_hour', type: 'number', label: 'Schedule · Run at hour', unit: '0–23', min: 0, max: 23, default: 1,
      description: 'Hour of the day the monthly report generates. 0 = midnight, 1 = 1:00 AM.' },
  ],
  payment_run: [
    { key: 'accounting_sources', type: 'multiselect', label: 'Accounting sources', options: [], default: [],
      description: 'Restrict payment scheduling to bills from specific connected accounting integrations. Leave all unchecked to include every connected source.' },
    { key: 'auto_pay_limit_cents', type: 'number', label: 'Auto-pay limit', penceDisplay: true, default: 100000,
      description: 'Bills up to this amount are automatically scheduled for payment without a human approver. Default £1,000.' },
    { key: 'approval_threshold_cents', type: 'number', label: 'Approval required above', penceDisplay: true, default: 250000,
      description: 'Bills above this amount are routed to a human approver before being added to the payment run. Default £2,500.' },
    { key: 'due_within_days', type: 'number', label: 'Pay bills due within', unit: 'days', default: 7,
      description: 'Only include bills in the payment run that are due within this many days. Prevents paying too far in advance and helps manage cash timing.' },
    { key: 'max_bills_per_run', type: 'number', label: 'Max bills per run', unit: 'bills', default: 50,
      description: 'Maximum number of bills included in a single payment run batch. Limits the size of any one run for easier review.' },
    { key: 'approval_deadline_days', type: 'number', label: 'Approval deadline', unit: 'days', min: 1, default: 3,
      description: 'Days a scheduled run waits for your approval before it auto-cancels. Approve within this window to release payment; miss it and the run is cancelled (you can reschedule it).' },
    { key: 'run_day_of_week', type: 'select', label: 'Schedule · Run day', options: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'], default: 'monday',
      description: 'Day of the week the automatic weekly payment run fires, in your organisation timezone (Settings).' },
    { key: 'run_hour', type: 'number', label: 'Schedule · Run at hour', unit: '0–23', min: 0, max: 23, default: 7,
      description: 'Hour of the day the weekly run fires. 0 = midnight, 7 = 7:00 AM.' },
  ],
  ar_collections: [
    { key: 'accounting_sources', type: 'multiselect', label: 'Accounting sources', options: [], default: [],
      description: 'Restrict collections to customer invoices from specific connected accounting integrations. Leave all unchecked to include every connected source.' },
    { key: 'reminder_1_days', type: 'number', label: 'First reminder after', unit: 'days overdue', min: 0, default: 0,
      description: 'Days past the due date to send a gentle first reminder. 0 = on the due date itself.' },
    { key: 'reminder_2_days', type: 'number', label: 'Second reminder after', unit: 'days overdue', min: 0, default: 7,
      description: 'Days overdue before a firmer second reminder is due.' },
    { key: 'final_notice_days', type: 'number', label: 'Final notice after', unit: 'days overdue', min: 0, default: 14,
      description: 'Days overdue before a final notice is issued. Final notices always route for approval.' },
    { key: 'escalate_days', type: 'number', label: 'Escalate after', unit: 'days overdue', min: 0, default: 30,
      description: 'Days overdue before the invoice is escalated (e.g. to a collections process). Escalations route for approval.' },
    { key: 'write_off_days', type: 'number', label: 'Write-off candidate after', unit: 'days overdue', min: 0, default: 120,
      description: 'Days overdue before an invoice is flagged as a write-off candidate. Write-offs always route for approval.' },
    { key: 'auto_send_reminders', type: 'boolean', label: 'Auto-send reminders', default: true,
      description: 'When on, gentle first and second reminders are auto-approved. Final notices, escalations, late fees, and write-offs always require approval regardless.' },
    { key: 'late_fee_percent', type: 'number', label: 'Late fee', unit: '%', step: 0.1, min: 0, max: 100, default: 0,
      description: 'Percentage late fee to recommend on overdue balances. 0 = no late fees. Any recommended late fee routes for approval.' },
    { key: 'late_fee_after_days', type: 'number', label: 'Late fee after', unit: 'days overdue', min: 0, default: 30,
      description: 'Days overdue before a late fee is recommended.',
      showWhen: (cfg) => Number(cfg['late_fee_percent']) > 0 },
    { key: 'write_off_max_cents', type: 'number', label: 'Auto write-off cap', penceDisplay: true, default: 5000,
      description: 'Write-off candidates above this amount always require approval; only balances below it can be suggested for a routine write-off.' },
  ],
}

export function getDefaultConfig(toolType: string): Record<string, unknown> {
  return Object.fromEntries((TOOL_FIELDS[toolType] ?? []).map(f => [f.key, f.default]))
}
