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
    slug: 'document-intelligence',
    type: 'document_intelligence',
    name: 'Document Intelligence',
    desc: 'Extract, validate and process invoices, receipts, and contracts using OCR and AI.',
    capabilities: [
      'OCR extraction from PDF, image, email attachments, and scanned receipts',
      'Invoice PO matching with configurable tolerance thresholds',
      'Contract term extraction — payment terms, renewal dates, penalty clauses',
      'Auto-approve low-value documents below spend threshold',
      'Multi-tier approval routing based on document value',
      'Duplicate detection across invoices, receipts, and contracts',
      'New vendor flagging and policy enforcement',
      'Submission deadline and receipt-required threshold enforcement',
    ],
  },
  {
    slug: 'ai-accountant',
    type: 'ai_accountant',
    name: 'AI Accountant',
    desc: 'Automate journal entries, categorisation, month-end close, and payroll reconciliation.',
    capabilities: [
      'Automatic transaction categorisation with confidence scoring',
      'Human review queue for low-confidence categorisations',
      'Learns from manual corrections over time',
      'Strict chart-of-accounts mode enforcement',
      'Month-end close orchestration — task tracking, reconciliation sign-offs, bottleneck detection',
      'Payroll reconciliation against HR data with ghost employee detection',
      'Payroll journal entry posting with automated approval routing',
      'Batch processing for high-volume transaction periods',
      'Configurable model retraining frequency',
    ],
  },
  {
    slug: 'spend-control',
    type: 'spend_control',
    name: 'Spend Control',
    desc: 'Process bills, enforce spend policies, detect duplicates, and route payments for approval.',
    capabilities: [
      'Automated bill processing from all connected accounting sources',
      'Duplicate detection by contact and amount within configurable window',
      'Per-transaction, daily, and monthly spend limit enforcement',
      'Pre-approval routing for high-value bills and expenses',
      'Category spend limits — meals, hotel per-diem, cash advances',
      'Receipt requirement enforcement above configurable threshold',
      'Real-time policy violation flagging before payment',
      'Multi-source aggregation: FreshBooks, Xero, QuickBooks',
    ],
  },
  {
    slug: 'ar-collections',
    type: 'ar_collections',
    name: 'AR & Collections',
    desc: 'Monitor outstanding invoices, classify urgency, automate debtor follow-ups and escalation.',
    capabilities: [
      'Real-time outstanding and overdue invoice monitoring',
      'AI urgency classification across all connected accounting sources',
      'Tiered reminder cadence — day 3, 14, 45, 90',
      'Automated chase email drafting per debtor',
      'Automatic escalation to legal referral',
      'Late fee calculation and application',
      'Write-off blocking above configurable outstanding threshold',
      'Per-debtor communication rate limiting and contact frequency caps',
      'Multi-source aggregation: FreshBooks, Xero, QuickBooks',
    ],
  },
  {
    slug: 'risk-compliance',
    type: 'risk_compliance',
    name: 'Risk & Compliance',
    desc: 'Detect fraud, monitor regulatory compliance, and maintain audit-ready records year-round.',
    capabilities: [
      'Risk-score-based transaction blocking and review thresholds',
      'Velocity detection within configurable time windows',
      'CTR threshold monitoring and structuring detection',
      'SAR auto-file controls (configurable)',
      'KYC refresh scheduling — standard and high-risk cadences',
      'PEP screening on all counterparties',
      'GDPR data retention enforcement',
      'Year-round audit preparation — evidence pack maintenance, PBC list management',
      'Periodic model retraining for fraud drift detection',
    ],
  },
  {
    slug: 'treasury-cash',
    type: 'treasury_cash',
    name: 'Treasury & Cash',
    desc: 'Monitor cash positions, forecast liquidity, track FX exposure, and monitor budget vs. actuals.',
    capabilities: [
      'Multi-bank balance aggregation and cash position tracking',
      'Runway and operating balance alerting',
      '30, 60, and 90-day cash flow bucketing from live accounting data',
      'Configurable rolling cash flow forecast with AI narrative',
      'FX exposure monitoring and unhedged position alerts',
      'Budget vs. actuals variance tracking with automatic explanations',
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
