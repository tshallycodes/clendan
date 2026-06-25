import type { Metadata } from 'next'
import { CodeBlock } from '@/components/dashboard/api/CodeBlock'
import { EndpointCard } from '@/components/dashboard/api/EndpointCard'

export const metadata: Metadata = { title: 'API Docs' }

const BASE_URL = 'https://api-production-0d35.up.railway.app/v1'

const TOOL_TYPES = [
  'invoice_processing',
  'receipt_processing',
  'expense_control',
  'collections',
  'fraud_detection',
  'treasury',
  'compliance',
  'reconciliation',
  'revenue_recognition',
  'ai_accountant',
  'credit_underwriting',
  'document_intelligence',
  'spend_control',
]

export default function ApiDocsPage() {
  return (
    <div className="p-6 space-y-10 max-w-4xl">

      <div>
        <h1 className="font-heading font-bold text-2xl text-brand-text">API Reference</h1>
        <p className="text-brand-muted text-xs font-mono mt-1">
          Trigger tools, poll results, manage approvals, and query audit trails.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Base URL</h2>
        <CodeBlock code={BASE_URL} lang="text" />
        <p className="text-xs font-mono text-brand-muted">
          All endpoints are versioned under <code className="text-brand-text">/v1</code>.
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Authentication</h2>
        <p className="text-xs font-mono text-brand-muted">
          All API calls require an <code className="text-brand-text">Authorization</code> header with a bearer API key.
          Generate keys from the <span className="text-brand-text">Developer</span> page.
        </p>
        <CodeBlock lang="bash" code={`curl ${BASE_URL}/execute \\
  -H "Authorization: ck_live_..."`} />
      </section>

      <section className="space-y-3">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Standard Response Shape</h2>
        <CodeBlock lang="json" code={`{
  "data":      { },
  "error":     null,
  "trace_id":  "trc_4c3879c5-7d59-...",
  "timestamp": "2026-06-24T10:00:00.000Z"
}`} />
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Idempotency</h2>
        <p className="text-xs font-mono text-brand-muted">
          All <code className="text-brand-text">POST</code> requests require an{' '}
          <code className="text-brand-text">Idempotency-Key</code> header. Sending the same key twice returns the
          original result without re-executing. Use a UUID per operation.
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Trigger a Tool</h2>
        <EndpointCard
          method="POST"
          path="/v1/execute"
          description="Enqueue a tool execution. Returns immediately with an execution_id. Poll for the result."
          headers={[
            { name: 'Authorization',  required: true,  description: 'ck_live_...' },
            { name: 'Idempotency-Key', required: true,  description: 'Unique key per operation (UUID recommended)' },
            { name: 'Content-Type',   required: true,  description: 'application/json' },
          ]}
          example={`curl -X POST ${BASE_URL}/execute \\
  -H "Authorization: ck_live_..." \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -H "Content-Type: application/json" \\
  -d '{
    "tool": "invoice_processing",
    "payload": {}
  }'`}
        />
        <CodeBlock lang="json" code={`{
  "data": {
    "execution_id": "exe_...",
    "status":       "queued",
    "decision":     "pending",
    "idempotent":   false
  },
  "error":     null,
  "trace_id":  "trc_...",
  "timestamp": "2026-06-24T10:00:00.000Z"
}`} />
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Poll Execution Result</h2>
        <EndpointCard
          method="GET"
          path="/v1/execute/{execution_id}"
          description="Fetch the current state of an execution. Poll until status is not queued or running."
          headers={[
            { name: 'Authorization', required: true, description: 'ck_live_...' },
          ]}
          example={`curl ${BASE_URL}/execute/<execution_id> \\
  -H "Authorization: ck_live_..."`}
        />
        <CodeBlock lang="json" code={`{
  "data": {
    "execution_id":    "exe_...",
    "status":          "completed",
    "decision":        "auto_approved",
    "confidence":      0.97,
    "reasoning_trace": "...",
    "duration_ms":     2340
  },
  "error":     null,
  "trace_id":  "trc_...",
  "timestamp": "2026-06-24T10:00:00.000Z"
}`} />
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">List Deployed Tools</h2>
        <EndpointCard
          method="GET"
          path="/v1/execute/tools"
          description="Returns all tools deployed for your tenant, including their type, autonomy level, and status."
          headers={[
            { name: 'Authorization', required: true, description: 'ck_live_...' },
          ]}
          example={`curl ${BASE_URL}/execute/tools \\
  -H "Authorization: ck_live_..."`}
        />
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Approvals</h2>
        <div className="space-y-3">
          <EndpointCard
            method="GET"
            path="/v1/execute/approvals"
            description="List all pending approval requests awaiting a human decision."
            headers={[
              { name: 'Authorization', required: true, description: 'ck_live_...' },
            ]}
            example={`curl ${BASE_URL}/execute/approvals \\
  -H "Authorization: ck_live_..."`}
          />
          <EndpointCard
            method="POST"
            path="/v1/execute/approvals/{id}/approve"
            description="Approve a pending action. Enforces expiry TTL — stale approvals are rejected."
            headers={[
              { name: 'Authorization',   required: true, description: 'ck_live_...' },
              { name: 'Idempotency-Key', required: true, description: 'Unique key per operation' },
            ]}
            example={`curl -X POST ${BASE_URL}/execute/approvals/<id>/approve \\
  -H "Authorization: ck_live_..." \\
  -H "Idempotency-Key: $(uuidgen)"`}
          />
          <EndpointCard
            method="POST"
            path="/v1/execute/approvals/{id}/reject"
            description="Reject a pending action. The execution is marked blocked and logged to the audit trail."
            headers={[
              { name: 'Authorization',   required: true, description: 'ck_live_...' },
              { name: 'Idempotency-Key', required: true, description: 'Unique key per operation' },
            ]}
            example={`curl -X POST ${BASE_URL}/execute/approvals/<id>/reject \\
  -H "Authorization: ck_live_..." \\
  -H "Idempotency-Key: $(uuidgen)"`}
          />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Audit Log</h2>
        <EndpointCard
          method="GET"
          path="/v1/execute/audit"
          description="Immutable append-only audit trail of every agent action taken for your tenant."
          headers={[
            { name: 'Authorization', required: true, description: 'ck_live_...' },
          ]}
          example={`curl "${BASE_URL}/execute/audit?limit=20&offset=0" \\
  -H "Authorization: ck_live_..."`}
        />
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Transactions</h2>
        <EndpointCard
          method="GET"
          path="/v1/execute/transactions"
          description="Paginated list of financial transactions synced and processed by your deployed tools."
          headers={[
            { name: 'Authorization', required: true, description: 'ck_live_...' },
          ]}
          example={`curl "${BASE_URL}/execute/transactions?limit=20&offset=0" \\
  -H "Authorization: ck_live_..."`}
        />
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Available Tool Types</h2>
        <p className="text-xs font-mono text-brand-muted">
          Pass one of these values as <code className="text-brand-text">tool</code> in the execute body.
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {TOOL_TYPES.map((t) => (
            <div
              key={t}
              className="bg-brand-bg border border-brand-border rounded-sm px-3 py-2 text-xs font-mono text-brand-text"
            >
              {t}
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Payload Reference</h2>
        <p className="text-xs font-mono text-brand-muted">
          Each tool accepts a <code className="text-brand-text">payload</code> object. Fields are optional — omitted fields
          fall back to what is configured in the tool&apos;s settings drawer.
        </p>

        {/* Reconciliation */}
        <div className="space-y-2">
          <p className="text-xs font-mono text-brand-text font-medium">reconciliation</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono border border-brand-border rounded-sm">
              <thead>
                <tr className="border-b border-brand-border bg-brand-elevated">
                  <th className="text-left px-3 py-2 text-brand-muted font-medium">Field</th>
                  <th className="text-left px-3 py-2 text-brand-muted font-medium">Type</th>
                  <th className="text-left px-3 py-2 text-brand-muted font-medium">Default</th>
                  <th className="text-left px-3 py-2 text-brand-muted font-medium">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border">
                {[
                  ['period_start', 'string (ISO date)', 'now − period_days', 'Start of the reconciliation window'],
                  ['period_end',   'string (ISO date)', 'now',               'End of the reconciliation window'],
                  ['period_days',  'integer',           '30',                'Window size when period_start is omitted'],
                  ['policy.unmatched_pct_threshold',    'float 0–1', '0.20', 'Fraction of unmatched items that triggers a policy breach'],
                  ['policy.match_amount_tolerance_pct', 'float 0–1', '0.01', 'Allowed % difference when matching amounts'],
                  ['policy.match_date_window_days',     'integer',   '30',   'Days either side of due date to still count as a match'],
                  ['policy.auto_match_confidence_min',  'float 0–1', '0.95', 'Minimum confidence for an auto-approved match'],
                  ['policy.stale_open_item_days',       'integer',   '90',   'Days before an unmatched item is flagged as stale'],
                  ['policy.include_reconciled',         'boolean',   'false','Include already-reconciled transactions in the run'],
                  ['policy.partial_match_enabled',      'boolean',   'true', 'Allow partial amount matches'],
                  ['policy.period_lock_respect',        'boolean',   'true', 'Reject edits to locked accounting periods'],
                ].map(([field, type, def, desc]) => (
                  <tr key={field} className="hover:bg-brand-elevated">
                    <td className="px-3 py-2 text-[#00C853]">{field}</td>
                    <td className="px-3 py-2 text-brand-muted">{type}</td>
                    <td className="px-3 py-2 text-brand-muted">{def}</td>
                    <td className="px-3 py-2 text-brand-secondary">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CodeBlock lang="json" code={`{
  "tool": "reconciliation",
  "payload": {
    "period_start": "2026-05-01",
    "period_end":   "2026-05-31",
    "policy": {
      "unmatched_pct_threshold":    0.3,
      "match_date_window_days":     60,
      "match_amount_tolerance_pct": 0.02,
      "include_reconciled":         false
    }
  }
}`} />
        </div>

        {/* Other tools */}
        <div className="space-y-2">
          <p className="text-xs font-mono text-brand-text font-medium">invoice_processing · receipt_processing · fraud_detection · expense_control · spend_control</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono border border-brand-border rounded-sm">
              <thead>
                <tr className="border-b border-brand-border bg-brand-elevated">
                  <th className="text-left px-3 py-2 text-brand-muted font-medium">Field</th>
                  <th className="text-left px-3 py-2 text-brand-muted font-medium">Type</th>
                  <th className="text-left px-3 py-2 text-brand-muted font-medium">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border">
                {[
                  ['invoice_id / receipt_id', 'string', 'ID of the document to process'],
                  ['amount_minor',  'integer', 'Amount in minor units (pence/cents) — no decimals'],
                  ['currency',      'string',  'ISO 4217 currency code (GBP, USD, EUR)'],
                  ['vendor / merchant', 'string', 'Counterparty name'],
                  ['transaction_id', 'string', 'Bank transaction ID (fraud_detection, expense_control)'],
                  ['employee_id',   'string',  'Employee reference (expense_control, spend_control)'],
                  ['category',      'string',  'Expense category (travel, software, meals, etc.)'],
                ].map(([field, type, desc]) => (
                  <tr key={field} className="hover:bg-brand-elevated">
                    <td className="px-3 py-2 text-[#00C853]">{field}</td>
                    <td className="px-3 py-2 text-brand-muted">{type}</td>
                    <td className="px-3 py-2 text-brand-secondary">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <p className="text-xs font-mono text-brand-muted">
          All payload fields are optional. Use the{' '}
          <span className="text-brand-text">API Playground</span> on the Developer page to see pre-filled
          examples for every tool type.
        </p>
      </section>

    </div>
  )
}
