export type IntegrationCategory = 'accounting' | 'banking' | 'documents' | 'payments'

export const INTEGRATION_CATEGORY_LABELS: Record<IntegrationCategory, string> = {
  accounting: 'Accounting',
  banking: 'Banking',
  documents: 'Documents',
  payments: 'Payments',
}

export interface ToolDef {
  slug: string
  type: string
  name: string
  desc: string
  capabilities: string[]
  // Integration categories this tool must have connected to produce output.
  // Empty means it runs with no connected integration (e.g. direct upload).
  requires: IntegrationCategory[]
  howItWorks?: { step: string; label: string; desc: string }[]
}

export const TOOLS: ToolDef[] = [
  {
    slug: 'reconciliation',
    type: 'reconciliation',
    requires: ['banking', 'accounting'],
    name: 'Reconciliation',
    desc: 'One click reconciles your bank, invoices, VAT, and payroll for any period. Flags every discrepancy before you close the books.',
    capabilities: [
      'Bank rec - matches every bank transaction against accounting invoices and bills, flags payments with no matching record',
      'Invoice rec - reviews all sales invoices for missing tax, overdue balances, and outstanding amounts',
      'VAT rec - totals output VAT from invoices, flags invoices with missing tax before you file your VAT return',
      'Payroll rec - cross-references payroll payments against your employee roster, detects ghost employees and salary discrepancies',
      'Run all four types in parallel with a single button - results in seconds for invoice and VAT, minutes for bank and payroll',
      'Drill into any rec type for full transaction-level detail and export to CSV',
      'Create journal entries directly from bank rec results to close unmatched items',
      'Full AI reasoning trace written to the audit log for every run',
    ],
  },
  {
    slug: 'document-intelligence',
    type: 'document_intelligence',
    requires: [],
    name: 'Invoice & Receipt Processing',
    desc: 'Drop in invoices and receipts. Clen reads each one, extracts the data, and turns it into a bill or an expense - invoices flow to Accounts Payable, receipts to Spend Control.',
    capabilities: [
      'Classifies every uploaded or synced document as an invoice, a receipt, or neither',
      'Invoices: extracts vendor, amount, due date, line items, and VAT',
      'Auto-approves in-policy invoices and writes the bill to your connected ERP',
      'Receipts: extracts merchant, amount, and category as an expense',
      'Routes anything above your thresholds to the Approvals queue',
      'Non-financial documents are recorded with no action - never analysed',
      'Duplicate invoice detection within a configurable window',
      'Supports PDF, Word (.docx), PNG, JPG, and WebP - up to 10 MB',
    ],
    howItWorks: [
      { step: '01', label: 'Ingest',   desc: 'Drop a file, or Clen pulls it from your connected Drive/Dropbox watch folder.' },
      { step: '02', label: 'Classify', desc: 'Claude reads the document and identifies it as an invoice, a receipt, or something else.' },
      { step: '03', label: 'Extract',  desc: 'For an invoice it pulls vendor, amount, due date, and line items; for a receipt, merchant, amount, and category.' },
      { step: '04', label: 'Route',    desc: 'Invoices become bills (Accounts Payable), receipts become expenses (Spend Control), within policy. Everything is audited.' },
    ],
  },
  {
    slug: 'spend-control',
    type: 'spend_control',
    requires: ['accounting'],
    name: 'Spend Control',
    desc: 'Process bills, enforce spend policies, detect duplicates, and route payments for approval.',
    capabilities: [
      'Automated bill processing from all connected accounting sources',
      'Duplicate detection by contact and amount within configurable window',
      'Per-transaction, daily, and monthly spend limit enforcement',
      'Pre-approval routing for high-value bills and expenses',
      'Category spend limits - meals, hotel per-diem, cash advances',
      'Receipt requirement enforcement above configurable threshold',
      'Real-time policy violation flagging before payment',
      'Multi-source aggregation: FreshBooks, Xero, QuickBooks',
    ],
  },
  {
    slug: 'tax-compliance',
    type: 'tax_compliance',
    requires: ['accounting'],
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
  {
    slug: 'financial-reporting',
    type: 'financial_reporting',
    requires: ['accounting', 'banking'],
    name: 'Financial Reporting',
    desc: 'Auto-generate P&L, balance sheet, and cash flow statements from live accounting data.',
    capabilities: [
      'Profit & loss statement with gross margin and net profit analysis',
      'Balance sheet summary - assets, liabilities, and net asset position',
      'Cash flow statement from live bank and payment data',
      'AI-generated CFO-level narrative and anomaly detection',
      'Approval routing when anomalies or at-risk health indicators are detected',
      'Configurable lookback period (30, 60, or 90 days)',
      'Multi-source aggregation: Xero, QuickBooks, FreshBooks, bank connections',
    ],
  },
  {
    slug: 'ar-collections',
    type: 'ar_collections',
    requires: ['accounting'],
    name: 'AR & Collections',
    desc: 'Chase overdue customer invoices automatically - ages every receivable and recommends the right collection action, from a gentle reminder to escalation.',
    capabilities: [
      'Ages every outstanding customer invoice by days overdue',
      'Tiered collection actions - reminder, second reminder, final notice, escalation',
      'Auto-sends gentle reminders within policy; routes firmer actions for approval',
      'Optional late fees above a configurable overdue threshold',
      'Write-off candidate flagging for long-overdue, low-value balances',
      'Runs daily on a schedule across all connected accounting sources',
      'Full aging breakdown and recommended-action list in the audit trail',
      'Multi-source aggregation: Xero, QuickBooks, FreshBooks',
    ],
    howItWorks: [
      { step: '01', label: 'Sync',   desc: 'Pulls outstanding customer invoices from your connected accounting sources.' },
      { step: '02', label: 'Age',    desc: 'Calculates days overdue for every unpaid invoice against its due date.' },
      { step: '03', label: 'Decide', desc: 'Assigns each invoice a collection action by tier and applies your late-fee and write-off rules.' },
      { step: '04', label: 'Route',  desc: 'Auto-approves reminders within policy; routes final notices, escalations, and write-offs for approval. Every run is audited.' },
    ],
  },
  {
    slug: 'payment-runs',
    type: 'payment_run',
    requires: ['accounting'],
    name: 'Payment Runs',
    desc: 'Automatically schedule approved supplier payments on a weekly cadence.',
    capabilities: [
      'Weekly automated payment run across all outstanding approved bills',
      'Auto-pay bills within configurable spend limit without manual intervention',
      'Approval routing for bills above the auto-pay threshold',
      'Duplicate and risk detection across the payment batch before scheduling',
      'Immutable PaymentRun record created per batch for full audit trail',
      'Configurable due-date window - only pays bills due within N days',
      'Blocked bills excluded automatically - no manual filtering required',
    ],
  },
]

export function slugToTool(slug: string): ToolDef | undefined {
  return TOOLS.find((t) => t.slug === slug)
}

// ─── Workflow grouping ────────────────────────────────────────────────────────
// The Tools page is organised by the two workflows the product runs end-to-end:
// AP (invoice processing) feeds Close (month-end). Each workflow lists its tools
// in pipeline order - the sequence a document travels through.

export interface WorkflowDef {
  id: 'accounts-payable' | 'accounts-receivable' | 'month-end-close'
  name: string
  headline: string
  tagline: string
  toolTypes: string[] // tool `type` values, in pipeline order
}

export const WORKFLOWS: WorkflowDef[] = [
  {
    id: 'accounts-payable',
    name: 'Accounts Payable',
    headline: 'From inbox to approved bill.',
    tagline: 'Invoices are ingested, read, coded, checked against your spend policy, and scheduled for payment - automatically.',
    toolTypes: ['document_intelligence', 'spend_control', 'payment_run'],
  },
  {
    id: 'accounts-receivable',
    name: 'Accounts Receivable',
    headline: 'From overdue to collected.',
    tagline: 'Every outstanding customer invoice is aged and chased with the right nudge - reminders, final notices, escalations - so cash comes in without manual follow-up.',
    toolTypes: ['ar_collections'],
  },
  {
    id: 'month-end-close',
    name: 'Month-End Close',
    headline: 'From reconciled to reported.',
    tagline: 'Every transaction matched, the tax position computed, and the books closed with full financial statements.',
    toolTypes: ['reconciliation', 'tax_compliance', 'financial_reporting'],
  },
]

/** Returns a workflow's tools in pipeline order, skipping any unknown types. */
export function toolsForWorkflow(workflow: WorkflowDef): ToolDef[] {
  return workflow.toolTypes
    .map((type) => TOOLS.find((t) => t.type === type))
    .filter((t): t is ToolDef => t !== undefined)
}
