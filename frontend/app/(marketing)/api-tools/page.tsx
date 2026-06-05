import Link from 'next/link'

// ─── Syntax helpers ────────────────────────────────────────────────────────────

function K({ children }: { children: React.ReactNode }) {
  return <span style={{ color: '#f5a623' }}>{children}</span>
}
function S({ children }: { children: React.ReactNode }) {
  return <span style={{ color: '#00C853' }}>{children}</span>
}
function N({ children }: { children: React.ReactNode }) {
  return <span style={{ color: '#00a8cc' }}>{children}</span>
}
function C({ children }: { children: React.ReactNode }) {
  return <span style={{ color: '#4a6a4a' }}>{children}</span>
}

// ─── Code block ────────────────────────────────────────────────────────────────

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre
      className="rounded-sm p-4 text-xs font-mono overflow-x-auto leading-relaxed"
      style={{ background: '#0a0a0f', border: '1px solid #1a2a1a' }}
    >
      {children}
    </pre>
  )
}

// ─── API sections ──────────────────────────────────────────────────────────────

function InvoiceParserSection() {
  return (
    <ApiSection
      endpoint="POST /v1/parse/invoice"
      title="Invoice Parser API"
      desc="Extracts vendor, amount, line items, due date, and VAT from any invoice format — PDF, image, or structured data."
      useCases={['Automated invoice ingestion', 'AP workflow automation', 'ERP data entry elimination']}
      curl={
        <>
          <K>curl</K> <S>-X POST</S> https://api.clendan.com/v1/parse/invoice \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Authorization: Bearer $TOKEN&quot;</S> \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Content-Type: application/json&quot;</S> \{'\n'}
          {'  '}<K>-d</K> <S>&apos;&#123;&quot;file_url&quot;: &quot;https://storage.example.com/inv-4821.pdf&quot;&#125;&apos;</S>
        </>
      }
      response={
        <>
          {'{'}{'\n'}
          {'  '}<K>&quot;data&quot;</K>: {'{'}{'\n'}
          {'    '}<K>&quot;vendor&quot;</K>: <S>&quot;Acme Corp Ltd&quot;</S>,{'\n'}
          {'    '}<K>&quot;amount_pence&quot;</K>: <N>38000</N>,{'\n'}
          {'    '}<K>&quot;currency&quot;</K>: <S>&quot;GBP&quot;</S>,{'\n'}
          {'    '}<K>&quot;due_date&quot;</K>: <S>&quot;2026-07-01&quot;</S>,{'\n'}
          {'    '}<K>&quot;vat_pence&quot;</K>: <N>6333</N>,{'\n'}
          {'    '}<K>&quot;line_items&quot;</K>: [{'\n'}
          {'      '}{'{'} <K>&quot;desc&quot;</K>: <S>&quot;Consulting services&quot;</S>, <K>&quot;qty&quot;</K>: <N>1</N>, <K>&quot;unit_pence&quot;</K>: <N>38000</N> {'}'}{'\n'}
          {'    '}]{'\n'}
          {'  }'},{'\n'}
          {'  '}<K>&quot;trace_id&quot;</K>: <S>&quot;cln_tr_8f4d2a&quot;</S>,{'\n'}
          {'  '}<K>&quot;timestamp&quot;</K>: <S>&quot;2026-06-05T09:14:32Z&quot;</S>{'\n'}
          {'}'}
        </>
      }
    />
  )
}

function ReceiptOcrSection() {
  return (
    <ApiSection
      endpoint="POST /v1/parse/receipt"
      title="Receipt OCR + Policy Check"
      desc="Extracts merchant, amount, category, and date from any receipt image, then validates the spend against your configured expense policy."
      useCases={['Expense claim automation', 'Policy violation detection', 'Receipt data extraction at scale']}
      curl={
        <>
          <K>curl</K> <S>-X POST</S> https://api.clendan.com/v1/parse/receipt \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Authorization: Bearer $TOKEN&quot;</S> \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Content-Type: application/json&quot;</S> \{'\n'}
          {'  '}<K>-d</K> <S>&apos;&#123;&quot;image_url&quot;: &quot;https://...&quot;, &quot;policy_id&quot;: &quot;pol_abc&quot;&#125;&apos;</S>
        </>
      }
      response={
        <>
          {'{'}{'\n'}
          {'  '}<K>&quot;data&quot;</K>: {'{'}{'\n'}
          {'    '}<K>&quot;merchant&quot;</K>: <S>&quot;Costa Coffee&quot;</S>,{'\n'}
          {'    '}<K>&quot;amount_pence&quot;</K>: <N>485</N>,{'\n'}
          {'    '}<K>&quot;category&quot;</K>: <S>&quot;meals_and_entertainment&quot;</S>,{'\n'}
          {'    '}<K>&quot;policy_result&quot;</K>: <S>&quot;approved&quot;</S>,{'\n'}
          {'    '}<K>&quot;confidence&quot;</K>: <N>0.98</N>{'\n'}
          {'  }'},{'\n'}
          {'  '}<K>&quot;trace_id&quot;</K>: <S>&quot;cln_tr_9a1b3c&quot;</S>,{'\n'}
          {'  '}<K>&quot;timestamp&quot;</K>: <S>&quot;2026-06-05T09:14:33Z&quot;</S>{'\n'}
          {'}'}
        </>
      }
    />
  )
}

function ReconcileSection() {
  return (
    <ApiSection
      endpoint="POST /v1/reconcile"
      title="Document Reconciliation"
      desc="Matches two financial datasets — bank transactions vs ledger entries, invoices vs payments — and returns matched, unmatched, and flagged rows."
      useCases={['Month-end close automation', 'Bank statement reconciliation', 'AP/AR mismatch detection']}
      curl={
        <>
          <K>curl</K> <S>-X POST</S> https://api.clendan.com/v1/reconcile \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Authorization: Bearer $TOKEN&quot;</S> \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Idempotency-Key: idem_xyz&quot;</S> \{'\n'}
          {'  '}<K>-d</K> <S>&apos;&#123;&quot;source_a_id&quot;: &quot;bank_stmt_jun&quot;, &quot;source_b_id&quot;: &quot;ledger_jun&quot;&#125;&apos;</S>
        </>
      }
      response={
        <>
          {'{'}{'\n'}
          {'  '}<K>&quot;data&quot;</K>: {'{'}{'\n'}
          {'    '}<K>&quot;matched&quot;</K>: <N>142</N>,{'\n'}
          {'    '}<K>&quot;unmatched&quot;</K>: <N>3</N>,{'\n'}
          {'    '}<K>&quot;flagged&quot;</K>: <N>1</N>,{'\n'}
          {'    '}<K>&quot;flagged_rows&quot;</K>: [{'\n'}
          {'      '}{'{'} <K>&quot;id&quot;</K>: <S>&quot;tx_44f1&quot;</S>, <K>&quot;reason&quot;</K>: <S>&quot;amount_mismatch&quot;</S>, <K>&quot;delta_pence&quot;</K>: <N>-200</N> {'}'}{'\n'}
          {'    '}]{'\n'}
          {'  }'},{'\n'}
          {'  '}<K>&quot;trace_id&quot;</K>: <S>&quot;cln_tr_2c8e5d&quot;</S>,{'\n'}
          {'  '}<K>&quot;timestamp&quot;</K>: <S>&quot;2026-06-05T09:14:34Z&quot;</S>{'\n'}
          {'}'}
        </>
      }
    />
  )
}

function FraudSection() {
  return (
    <ApiSection
      endpoint="POST /v1/fraud/score"
      title="Fraud Signal API"
      desc="Returns a risk score between 0 and 1 with structured reasoning for any transaction. Integrates into your approval flow or triggers automatic blocks."
      useCases={['Real-time payment fraud screening', 'Anomaly detection in expense claims', 'Pre-authorisation risk scoring']}
      curl={
        <>
          <K>curl</K> <S>-X POST</S> https://api.clendan.com/v1/fraud/score \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Authorization: Bearer $TOKEN&quot;</S> \{'\n'}
          {'  '}<K>-d</K> <S>&apos;&#123;&quot;transaction_id&quot;: &quot;tx_44f1&quot;, &quot;amount_pence&quot;: 95000, &quot;vendor&quot;: &quot;Unknown Ltd&quot;&#125;&apos;</S>
        </>
      }
      response={
        <>
          {'{'}{'\n'}
          {'  '}<K>&quot;data&quot;</K>: {'{'}{'\n'}
          {'    '}<K>&quot;score&quot;</K>: <N>0.87</N>,{'\n'}
          {'    '}<K>&quot;verdict&quot;</K>: <S>&quot;high_risk&quot;</S>,{'\n'}
          {'    '}<K>&quot;signals&quot;</K>: [{'\n'}
          {'      '}<S>&quot;first_transaction_with_vendor&quot;</S>,{'\n'}
          {'      '}<S>&quot;amount_3x_above_average&quot;</S>,{'\n'}
          {'      '}<S>&quot;unusual_hour&quot;</S>{'\n'}
          {'    '}],{'\n'}
          {'    '}<C>// Full reasoning trace available at data.reasoning</C>{'\n'}
          {'    '}<K>&quot;reasoning&quot;</K>: <S>&quot;Transaction deviates from 90-day baseline...&quot;</S>{'\n'}
          {'  }'},{'\n'}
          {'  '}<K>&quot;trace_id&quot;</K>: <S>&quot;cln_tr_7d3f1b&quot;</S>,{'\n'}
          {'  '}<K>&quot;timestamp&quot;</K>: <S>&quot;2026-06-05T09:14:35Z&quot;</S>{'\n'}
          {'}'}
        </>
      }
    />
  )
}

function ContractSection() {
  return (
    <ApiSection
      endpoint="POST /v1/parse/contract"
      title="Contract Extraction"
      desc="Extracts counterparty, payment terms, renewal dates, and key obligations from any contract PDF. Structured output ready for your workflow."
      useCases={['Contract management automation', 'Renewal date alerting', 'Payment terms extraction for AP']}
      curl={
        <>
          <K>curl</K> <S>-X POST</S> https://api.clendan.com/v1/parse/contract \{'\n'}
          {'  '}<K>-H</K> <S>&quot;Authorization: Bearer $TOKEN&quot;</S> \{'\n'}
          {'  '}<K>-d</K> <S>&apos;&#123;&quot;file_url&quot;: &quot;https://storage.example.com/contract-2026.pdf&quot;&#125;&apos;</S>
        </>
      }
      response={
        <>
          {'{'}{'\n'}
          {'  '}<K>&quot;data&quot;</K>: {'{'}{'\n'}
          {'    '}<K>&quot;counterparty&quot;</K>: <S>&quot;Globex Corporation&quot;</S>,{'\n'}
          {'    '}<K>&quot;payment_terms&quot;</K>: <S>&quot;Net 30&quot;</S>,{'\n'}
          {'    '}<K>&quot;renewal_date&quot;</K>: <S>&quot;2027-01-15&quot;</S>,{'\n'}
          {'    '}<K>&quot;auto_renews&quot;</K>: <N>true</N>,{'\n'}
          {'    '}<K>&quot;obligations&quot;</K>: [{'\n'}
          {'      '}<S>&quot;Monthly SLA report by 5th of month&quot;</S>,{'\n'}
          {'      '}<S>&quot;90-day termination notice required&quot;</S>{'\n'}
          {'    '}]{'\n'}
          {'  }'},{'\n'}
          {'  '}<K>&quot;trace_id&quot;</K>: <S>&quot;cln_tr_1a5e9c&quot;</S>,{'\n'}
          {'  '}<K>&quot;timestamp&quot;</K>: <S>&quot;2026-06-05T09:14:36Z&quot;</S>{'\n'}
          {'}'}
        </>
      }
    />
  )
}

// ─── Shared section layout ─────────────────────────────────────────────────────

interface ApiSectionProps {
  endpoint: string
  title: string
  desc: string
  useCases: string[]
  curl: React.ReactNode
  response: React.ReactNode
}

function ApiSection({ endpoint, title, desc, useCases, curl, response }: ApiSectionProps) {
  return (
    <section className="border-t border-brand-border py-14">
      <div className="grid md:grid-cols-2 gap-10 items-start">
        {/* Left: info */}
        <div>
          <span
            className="inline-block font-mono text-xs px-3 py-1 rounded-sm mb-4"
            style={{ background: 'rgba(245,166,35,0.08)', border: '1px solid rgba(245,166,35,0.2)', color: '#f5a623' }}
          >
            {endpoint}
          </span>
          <h2
            className="font-heading font-bold text-2xl mb-3"
            style={{ fontFamily: 'var(--font-heading)' }}
          >
            {title}
          </h2>
          <p className="font-mono text-sm text-brand-secondary mb-6 leading-relaxed">{desc}</p>
          <ul className="space-y-1.5">
            {useCases.map((u) => (
              <li key={u} className="flex items-start gap-2 font-mono text-xs text-brand-secondary">
                <span className="text-brand-green mt-0.5">→</span>
                {u}
              </li>
            ))}
          </ul>
        </div>

        {/* Right: code */}
        <div className="space-y-3">
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted">Request</p>
          <CodeBlock>{curl}</CodeBlock>
          <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted pt-2">Response</p>
          <CodeBlock>{response}</CodeBlock>
        </div>
      </div>
    </section>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ApiToolsPage() {
  return (
    <div className="bg-brand-bg text-brand-text">

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 pt-20 pb-8">
        <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-4">API Tools</p>
        <h1
          className="text-4xl md:text-5xl font-heading font-extrabold leading-tight mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          5 APIs. Plug Into<br />
          <span className="text-brand-green">Any Stack.</span>
        </h1>
        <p className="font-mono text-sm text-brand-secondary max-w-xl">
          Use them inside Clendan or call them directly. JSON in, JSON out.
        </p>
      </section>

      {/* API sections */}
      <div className="max-w-6xl mx-auto px-6 md:px-8">
        <InvoiceParserSection />
        <ReceiptOcrSection />
        <ReconcileSection />
        <FraudSection />
        <ContractSection />
      </div>

      {/* Pricing note */}
      <section className="border-t border-brand-border bg-brand-surface">
        <div className="max-w-6xl mx-auto px-6 md:px-8 py-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-brand-muted mb-1">Pricing</p>
            <p className="font-mono text-sm text-brand-secondary">
              Standalone API access included in Growth and Enterprise plans.
            </p>
          </div>
          <Link
            href="/pricing"
            className="border border-brand-border text-brand-text hover:bg-brand-bg rounded-sm px-5 py-2.5 text-sm font-mono transition-colors whitespace-nowrap"
          >
            View Pricing →
          </Link>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 md:px-8 py-20 text-center">
        <h2
          className="font-heading font-bold text-3xl mb-4"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          Start building with Clendan APIs
        </h2>
        <p className="font-mono text-sm text-brand-secondary mb-8">
          Full API docs, rate limits, and sandbox credentials in the developer portal.
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link
            href="/sign-up"
            className="inline-block rounded-sm px-6 py-3 text-sm font-mono font-medium transition-colors hover:bg-[#00a844]"
            style={{ background: '#00C853', color: '#000' }}
          >
            Get API Access →
          </Link>
          <Link
            href="/docs"
            className="inline-block border border-brand-border text-brand-text hover:bg-brand-surface rounded-sm px-6 py-3 text-sm font-mono transition-colors"
          >
            View Docs
          </Link>
        </div>
      </section>

    </div>
  )
}
