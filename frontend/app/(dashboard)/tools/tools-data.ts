export interface ToolDef {
  slug: string
  type: string
  name: string
  desc: string
  capabilities: string[]
}

export const TOOLS: ToolDef[] = [
  {
    slug: 'reconciliation',
    type: 'reconciliation',
    name: 'Reconciliation',
    desc: 'Match bank transactions against invoices. Detects unmatched items and flags anomalies.',
    capabilities: [
      'Match bank transactions against invoices within configurable tolerances',
      'Flag unmatched, flagged, and review-required items per run',
      'Export reconciliation results to CSV',
      'Configurable amount and date tolerance windows',
      'Stale open-item detection and alerting',
    ],
  },
  {
    slug: 'invoice-processing',
    type: 'invoice_processing',
    name: 'Invoice Processing',
    desc: 'Extract, validate and process invoices from documents and email.',
    capabilities: [
      'OCR extraction from PDF, image, and email attachments',
      'PO matching with configurable tolerance thresholds',
      'Auto-approve invoices below spend threshold',
      'Multi-tier approval routing based on invoice value',
      'Duplicate detection across configurable look-back window',
      'New vendor flagging and policy enforcement',
    ],
  },
  {
    slug: 'ai-accountant',
    type: 'ai_accountant',
    name: 'AI Accountant',
    desc: 'Automate journal entries, categorisation and month-end close.',
    capabilities: [
      'Automatic transaction categorisation with confidence scoring',
      'Human review queue for low-confidence categorisations',
      'Learns from manual corrections over time',
      'Strict chart-of-accounts mode enforcement',
      'Batch processing for high-volume transaction periods',
      'Configurable model retraining frequency',
    ],
  },
  {
    slug: 'receipt-processing',
    type: 'receipt_processing',
    name: 'Receipt Processing',
    desc: 'Extract and categorise expenses from receipts using OCR and AI.',
    capabilities: [
      'OCR extraction from photos and scanned receipts',
      'Auto-approve low-value receipts below threshold',
      'Submission deadline enforcement with grace periods',
      'Duplicate receipt detection across rolling window',
      'Configurable OCR confidence minimum',
      'Receipt-required threshold enforcement',
    ],
  },
  {
    slug: 'expense-control',
    type: 'expense_control',
    name: 'Expense Control',
    desc: 'Enforce spend policies and flag out-of-policy expenses before payment.',
    capabilities: [
      'Per-transaction, daily, and monthly spend limit enforcement',
      'Receipt requirement above configurable threshold',
      'Pre-approval routing for high-value expenses',
      'Category limits (meals, hotel per-diem)',
      'Cash advance controls',
      'Real-time policy violation flagging before payment',
    ],
  },
  {
    slug: 'collections',
    type: 'collections',
    name: 'Collections',
    desc: 'Automate follow-ups on overdue invoices and manage debtor communication.',
    capabilities: [
      'Tiered reminder cadence (day 3, 14, 45, 90)',
      'Automatic escalation to legal referral',
      'Late fee calculation and application',
      'Minimum balance threshold for collections triggering',
      'Per-debtor communication rate limiting',
      'Configurable call and contact frequency caps',
    ],
  },
  {
    slug: 'fraud-detection',
    type: 'fraud_detection',
    name: 'Fraud Detection',
    desc: 'Detect suspicious transactions and policy violations in real-time.',
    capabilities: [
      'Risk-score-based block and review thresholds',
      'Velocity detection within configurable time windows',
      'Single transaction amount caps',
      'New merchant and unusual-hour risk boosting',
      'Real-time transaction stream monitoring',
      'Periodic model retraining for drift detection',
    ],
  },
  {
    slug: 'treasury',
    type: 'treasury',
    name: 'Treasury',
    desc: 'Monitor cash positions, forecast liquidity and manage working capital.',
    capabilities: [
      'Multi-bank balance aggregation and cash position tracking',
      'Runway and operating balance alerting',
      'Configurable rolling cash flow forecast',
      'Payroll reserve buffer enforcement',
      'Bank counterparty concentration limits',
      'Optional automated cash sweep execution',
    ],
  },
  {
    slug: 'revenue-recognition',
    type: 'revenue_recognition',
    name: 'Revenue Recognition',
    desc: 'Automate ASC 606 / IFRS 15 revenue recognition schedules.',
    capabilities: [
      'ASC 606 and IFRS 15 recognition schedule generation',
      'Point-in-time and over-time recognition methods',
      'Variable consideration constraint enforcement',
      'Daily or monthly recognition frequency',
      'Period lock enforcement for closed periods',
      'Expected value and most-likely-amount estimation',
    ],
  },
  {
    slug: 'credit-underwriting',
    type: 'credit_underwriting',
    name: 'Credit Underwriting',
    desc: 'Assess credit risk and generate underwriting decisions.',
    capabilities: [
      'Automated credit score and DTI ratio evaluation',
      'Auto-approve decisions above score threshold',
      'LTV ratio enforcement for secured lending',
      'Employment duration validation',
      'Maximum loan amount controls',
      'Automatic adverse action notice generation',
    ],
  },
  {
    slug: 'compliance',
    type: 'compliance',
    name: 'Compliance',
    desc: 'Monitor transactions against regulatory rules and internal policies.',
    capabilities: [
      'CTR threshold monitoring and filing',
      'Structuring detection within rolling time windows',
      'SAR auto-file controls (configurable)',
      'KYC refresh scheduling (standard and high-risk)',
      'PEP screening on counterparties',
      'GDPR data retention enforcement',
    ],
  },
  {
    slug: 'accounts-receivable',
    type: 'accounts_receivable',
    name: 'Accounts Receivable',
    desc: 'Monitor outstanding invoices, classify urgency, and draft collection actions.',
    capabilities: [
      'Real-time outstanding and overdue invoice monitoring',
      'AI urgency classification across all connected accounting sources',
      'Automated chase email drafting per debtor',
      'Write-off blocking above configurable outstanding threshold',
      'Multi-source aggregation: FreshBooks, Xero, QuickBooks',
      'Approval routing for write-off and escalation actions',
    ],
  },
  {
    slug: 'accounts-payable',
    type: 'accounts_payable',
    name: 'Accounts Payable',
    desc: 'Process bills, detect duplicates, and route payments for approval.',
    capabilities: [
      'Automated bill processing from all connected sources',
      'Duplicate detection by contact and amount within configurable window',
      'Auto-approve payments below spend threshold',
      'Approval routing for high-value bills',
      'Overdue bill flagging with escalation',
      'Multi-source aggregation: FreshBooks, Xero, QuickBooks',
    ],
  },
  {
    slug: 'cash-flow-forecast',
    type: 'cash_flow_forecast',
    name: 'Cash Flow Forecast',
    desc: 'Bucket AR inflows and AP outflows to forecast 30/60/90-day liquidity.',
    capabilities: [
      '30, 60, and 90-day cash flow bucketing from live accounting data',
      'Low runway alerting below configurable threshold',
      'AR inflow and AP outflow breakdown per period',
      'AI narrative with scenario and risk commentary',
      'Approval routing when net cash position drops below floor',
      'Multi-source aggregation: FreshBooks, Xero, QuickBooks',
    ],
  },
  {
    slug: 'tax-compliance',
    type: 'tax_compliance',
    name: 'Tax Compliance',
    desc: 'Compute VAT position, detect missing tax codes, and flag filing risks.',
    capabilities: [
      'VAT collected and input VAT computation from live invoice and expense data',
      'Net VAT liability or reclaim position calculation',
      'Missing tax code detection across bills and expenses',
      'AI-generated filing risk summary and recommendations',
      'Approval routing when liability exceeds configurable threshold',
      'Multi-source aggregation: FreshBooks, Xero, QuickBooks',
    ],
  },
]

export function slugToTool(slug: string): ToolDef | undefined {
  return TOOLS.find((t) => t.slug === slug)
}
