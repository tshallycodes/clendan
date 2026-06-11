import Link from 'next/link'
import { WorkerFilters } from './WorkerFilters'

const WORKERS = [
  {
    name: 'Invoice Processing Tool',
    phase: 'MVP' as const,
    desc: 'Ingests invoices, extracts data, validates against contracts, routes for approval, schedules payment.',
    tools: ['invoice_ingestion_api', 'ocr_document_tool', 'accounting_api', 'payment_scheduler_api'],
  },
  {
    name: 'AI Accountant Tool',
    phase: 'MVP' as const,
    desc: 'Categorises bank transactions, matches invoices to payments, updates ledger, detects reconciliation errors.',
    tools: ['bank_transaction_api', 'accounting_ledger_api', 'invoice_system_api'],
  },
  {
    name: 'Reconciliation Tool',
    phase: 'V2' as const,
    desc: 'Aggregates multi-source data, matches transactions, flags mismatches, generates reconciliation reports.',
    tools: ['bank_aggregation_api', 'erp_sync_api'],
  },
  {
    name: 'Expense Control Tool',
    phase: 'V2' as const,
    desc: 'Reviews expense claims, validates receipts, enforces spending policies, approves or rejects with audit trail.',
    tools: ['expense_api', 'receipt_ocr_tool', 'policy_engine_api'],
  },
  {
    name: 'Collections Tool',
    phase: 'V2' as const,
    desc: 'Detects overdue invoices, segments by risk, sends reminders, escalates collection efforts.',
    tools: ['CRM_api', 'messaging_api', 'invoicing_api'],
  },
  {
    name: 'Fraud Detection Tool',
    phase: 'V2' as const,
    desc: 'Monitors transactions in real time, detects anomalies, flags suspicious patterns, triggers blocks.',
    tools: ['transaction_stream_api', 'anomaly_detection_model'],
  },
  {
    name: 'Treasury Tool',
    phase: 'V2' as const,
    desc: 'Aggregates balances, forecasts cash flow, detects liquidity risks, recommends transfers.',
    tools: ['bank_aggregation_api', 'forecasting_model'],
  },
  {
    name: 'Revenue Recognition Tool',
    phase: 'V2' as const,
    desc: 'Parses contracts, tracks subscription data, applies ASC 606 rules, generates revenue schedules.',
    tools: ['contract_parser_api', 'billing_usage_api', 'ledger_api'],
  },
  {
    name: 'Credit Underwriting Tool',
    phase: 'V3' as const,
    desc: 'Evaluates credit risk, processes bureau and bank data, approves or rejects lending applications.',
    tools: ['credit_bureau_api', 'bank_data_api', 'risk_scoring_model'],
  },
  {
    name: 'Compliance Tool',
    phase: 'V3' as const,
    desc: 'Monitors for regulatory violations, generates audit logs, prepares compliance reports.',
    tools: ['transaction_stream_api', 'regulatory_rules_engine', 'audit_log_system'],
  },
]

export type Worker = typeof WORKERS[number]

export default function WorkersPage() {
  return (
    <div className="bg-brand-bg text-brand-text">

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-12">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">Tools</p>
        <h1
          className="text-4xl md:text-5xl font-heading font-extrabold leading-tight mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          10 AI Tools.<br />
          <span className="text-brand-green">Built for Every Finance Function.</span>
        </h1>
        <p className="font-mono text-sm text-brand-secondary max-w-xl">
          Each tool is a specialised sub-agent with a defined role, integrations, and policy rules.
          Deploy one or deploy all.
        </p>
      </section>

      {/* Filters + Grid (client) */}
      <WorkerFilters workers={WORKERS} />

      {/* Architecture callout */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 py-8 pb-16">
        <div
          className="bg-brand-surface rounded-sm p-6 border border-brand-border"
          style={{ borderLeft: '4px solid #00C853' }}
        >
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-2">Architecture</p>
          <p className="font-mono text-sm text-brand-text">
            Tools never call each other.{' '}
            <span className="text-brand-secondary">
              All coordination flows through the Financial Orchestrator.
            </span>
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-brand-border">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-20 text-center">
          <h2
            className="font-heading font-bold text-3xl mb-4"
            style={{ fontFamily: 'var(--font-heading)' }}
          >
            Start with the Invoice Processing Tool
          </h2>
          <p className="font-mono text-sm text-brand-secondary mb-8">
            The most deployed tool in Clendan. Live in under 10 minutes.
          </p>
          <Link
            href="/sign-up"
            className="inline-block rounded-sm px-6 py-3 text-sm font-mono font-medium transition-colors hover:bg-[#00a844]"
            style={{ background: '#00C853', color: '#000' }}
          >
            Deploy Invoice Processing Tool →
          </Link>
        </div>
      </section>

    </div>
  )
}
