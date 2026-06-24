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

    </div>
  )
}
