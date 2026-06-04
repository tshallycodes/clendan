import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { CodeBlock } from '@/components/dashboard/api/CodeBlock'
import { EndpointCard } from '@/components/dashboard/api/EndpointCard'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export default function ApiDocsPage() {
  return (
    <div className="p-6 space-y-10 max-w-4xl">

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-heading font-bold text-2xl text-brand-text">Developer API</h1>
          <p className="text-brand-muted text-xs font-mono mt-1">
            Connect your systems to Clendan — trigger agents, respond to approvals, query audit trails.
          </p>
        </div>
        <Link
          href={`${BASE_URL}/docs`}
          target="_blank"
          className="shrink-0 flex items-center gap-2 text-xs font-mono text-brand-green border border-brand-green/30 bg-brand-green/08 px-3 py-2 rounded-sm hover:bg-brand-green/15 transition-colors"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Interactive docs
        </Link>
      </div>

      {/* Base URL */}
      <section className="space-y-3">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Base URL</h2>
        <CodeBlock code={`${BASE_URL}/v1`} lang="text" />
        <p className="text-xs font-mono text-brand-muted">
          All endpoints are versioned under <code className="text-brand-text">/v1</code>.
          Every response has the shape:
        </p>
        <CodeBlock lang="json" code={`{
  "data":      { ... },
  "error":     null,
  "trace_id":  "4c3879c5-7d59-...",
  "timestamp": "2026-06-04T21:18:12.982Z"
}`} />
      </section>

      {/* Authentication */}
      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Authentication</h2>
        <p className="text-xs font-mono text-brand-muted">
          Dashboard endpoints use a short-lived Clerk JWT.
          Agent execution endpoints use your <code className="text-brand-text">X-Tenant-ID</code> paired with an <code className="text-brand-text">Idempotency-Key</code>.
        </p>
        <CodeBlock lang="bash" code={`# Obtain a Clerk session token (browser / server SDK)
TOKEN=$(clerk session token)

# Pass it on every dashboard request
curl -H "Authorization: Bearer $TOKEN" \\
     ${BASE_URL}/v1/dashboard/stats`} />
      </section>

      {/* Onboarding */}
      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Onboarding</h2>
        <EndpointCard
          method="POST" path="/v1/onboarding"
          description="Create your tenant and user on first sign-in. Safe to call multiple times — idempotent."
          headers={[{ name: 'Authorization', required: true, description: 'Bearer <clerk-token>' }]}
          example={`curl -X POST ${BASE_URL}/v1/onboarding \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"tenant_name": "Acme Corp"}'`}
        />
      </section>

      {/* Dashboard */}
      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Dashboard</h2>
        <div className="space-y-3">
          <EndpointCard
            method="GET" path="/v1/dashboard/stats"
            description="Execution counts, pending approvals, active workers, invoices processed."
            headers={[{ name: 'Authorization', required: true, description: 'Bearer <clerk-token>' }]}
            example={`curl ${BASE_URL}/v1/dashboard/stats \\
  -H "Authorization: Bearer $TOKEN"`}
          />
          <EndpointCard
            method="GET" path="/v1/dashboard/executions"
            description="Paginated list of agent executions for your tenant, newest first."
            headers={[{ name: 'Authorization', required: true, description: 'Bearer <clerk-token>' }]}
            example={`curl "${BASE_URL}/v1/dashboard/executions?limit=20&offset=0" \\
  -H "Authorization: Bearer $TOKEN"`}
          />
          <EndpointCard
            method="GET" path="/v1/dashboard/approvals"
            description="All pending human-approval requests awaiting a decision."
            headers={[{ name: 'Authorization', required: true, description: 'Bearer <clerk-token>' }]}
            example={`curl ${BASE_URL}/v1/dashboard/approvals \\
  -H "Authorization: Bearer $TOKEN"`}
          />
          <EndpointCard
            method="GET" path="/v1/dashboard/audit"
            description="Immutable audit trail — append-only log of every agent action."
            headers={[{ name: 'Authorization', required: true, description: 'Bearer <clerk-token>' }]}
            example={`curl ${BASE_URL}/v1/dashboard/audit \\
  -H "Authorization: Bearer $TOKEN"`}
          />
        </div>
      </section>

      {/* Agents */}
      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Agent Execution</h2>
        <p className="text-xs font-mono text-brand-muted">
          Trigger a worker with a document. Use the same <code className="text-brand-text">Idempotency-Key</code> to safely retry — duplicate requests return the existing execution record.
        </p>
        <EndpointCard
          method="POST" path="/v1/agents/{worker_id}/run"
          description="Enqueue a document for processing by a specific worker. Returns immediately with execution_id."
          headers={[
            { name: 'X-Tenant-ID',      required: true, description: 'Your tenant ID' },
            { name: 'Idempotency-Key',  required: true, description: 'Unique key per operation (UUID recommended)' },
          ]}
          example={`# Encode document as base64, then submit
FILE_B64=$(base64 -w0 invoice.pdf)

curl -X POST ${BASE_URL}/v1/agents/<worker_id>/run \\
  -H "X-Tenant-ID: <your-tenant-id>" \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -H "Content-Type: application/json" \\
  -d "{
    \\"file_bytes_b64\\": \\"$FILE_B64\\",
    \\"content_type\\": \\"application/pdf\\"
  }"`}
        />
      </section>

      {/* Approvals */}
      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Approvals</h2>
        <EndpointCard
          method="POST" path="/v1/approvals/{approval_id}/respond"
          description="Approve or reject a pending action. Enforces expiry TTL — stale approvals are rejected with 410."
          headers={[
            { name: 'X-Tenant-ID', required: true, description: 'Your tenant ID' },
          ]}
          example={`curl -X POST ${BASE_URL}/v1/approvals/<approval_id>/respond \\
  -H "X-Tenant-ID: <your-tenant-id>" \\
  -H "Content-Type: application/json" \\
  -d '{"action": "approve", "responder_id": "<your-user-id>"}'

# To reject:
# -d '{"action": "reject", "responder_id": "<your-user-id>"}'`}
        />
      </section>

      {/* Python SDK example */}
      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">Python example</h2>
        <CodeBlock lang="python" code={`import base64, uuid, httpx

BASE = "${BASE_URL}/v1"
TENANT_ID = "<your-tenant-id>"
WORKER_ID = "<your-worker-id>"

with open("invoice.pdf", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

resp = httpx.post(
    f"{BASE}/agents/{WORKER_ID}/run",
    headers={
        "X-Tenant-ID":     TENANT_ID,
        "Idempotency-Key": str(uuid.uuid4()),
    },
    json={"file_bytes_b64": b64, "content_type": "application/pdf"},
)
print(resp.json()["data"])  # {"execution_id": "...", "status": "queued"}`} />
      </section>

      {/* TypeScript SDK example */}
      <section className="space-y-4">
        <h2 className="font-heading font-semibold text-sm text-brand-text uppercase tracking-widest">TypeScript example</h2>
        <CodeBlock lang="typescript" code={`const BASE = "${BASE_URL}/v1"
const TENANT_ID = "<your-tenant-id>"
const WORKER_ID = "<your-worker-id>"

const fileBytes = await fs.readFile("invoice.pdf")
const b64 = fileBytes.toString("base64")

const res = await fetch(\`\${BASE}/agents/\${WORKER_ID}/run\`, {
  method: "POST",
  headers: {
    "X-Tenant-ID":     TENANT_ID,
    "Idempotency-Key": crypto.randomUUID(),
    "Content-Type":    "application/json",
  },
  body: JSON.stringify({ file_bytes_b64: b64, content_type: "application/pdf" }),
})

const { data } = await res.json()
console.log(data.execution_id, data.status) // "queued"`} />
      </section>

    </div>
  )
}
