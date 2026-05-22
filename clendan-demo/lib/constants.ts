export const WORKERS = [
  {
    id: "invoice-processing",
    name: "Invoice Processing Worker",
    description: "Receives, parses, validates, and routes invoices automatically. Creates bills in your ERP and schedules payments.",
    badge: "MVP" as const,
    tools: ["Invoice Parser API", "Xero", "QuickBooks", "Policy Engine"],
    status: "active" as const,
  },
  {
    id: "ai-accountant",
    name: "AI Accountant Worker",
    description: "Categorises transactions, reconciles accounts, and closes the books. Flags anomalies for human review.",
    badge: "MVP" as const,
    tools: ["Plaid", "Xero", "QuickBooks", "Reconciliation API"],
    status: "active" as const,
  },
  {
    id: "reconciliation",
    name: "Reconciliation Worker",
    description: "Compares bank feeds against ledger entries in real time. Detects drift and triggers alerts.",
    badge: "V2" as const,
    tools: ["Plaid", "TrueLayer", "Xero", "Reconciliation API"],
    status: "inactive" as const,
  },
  {
    id: "expense-control",
    name: "Expense Control Worker",
    description: "Validates expense submissions against policy. Approves, rejects, or escalates based on rules.",
    badge: "V2" as const,
    tools: ["Receipt OCR API", "Policy Engine", "Slack"],
    status: "inactive" as const,
  },
  {
    id: "collections",
    name: "Collections Worker",
    description: "Chases overdue invoices with escalating reminders. Triggers payment collection via GoCardless.",
    badge: "V2" as const,
    tools: ["GoCardless", "Resend", "Stripe", "InvoiceFlow API"],
    status: "inactive" as const,
  },
  {
    id: "fraud-detection",
    name: "Fraud Detection Worker",
    description: "Scores every transaction for fraud risk using Stripe Radar signals and internal baselines.",
    badge: "V2" as const,
    tools: ["Fraud Signal API", "Stripe Radar", "Policy Engine"],
    status: "inactive" as const,
  },
  {
    id: "treasury",
    name: "Treasury Worker",
    description: "Monitors cash positions across accounts and optimises fund allocation against targets.",
    badge: "V2" as const,
    tools: ["Plaid", "TrueLayer", "Policy Engine"],
    status: "inactive" as const,
  },
  {
    id: "revenue-recognition",
    name: "Revenue Recognition Worker",
    description: "Automates ASC 606 / IFRS 15 revenue scheduling from Stripe subscription data.",
    badge: "V2" as const,
    tools: ["Stripe Billing", "Xero", "QuickBooks"],
    status: "inactive" as const,
  },
  {
    id: "credit-underwriting",
    name: "Credit Underwriting Worker",
    description: "Evaluates creditworthiness using financial data and pre-computed credit signals.",
    badge: "V3" as const,
    tools: ["Plaid", "DebtStack API", "Policy Engine"],
    status: "inactive" as const,
  },
  {
    id: "compliance",
    name: "Compliance Worker",
    description: "Monitors transactions for AML patterns and regulatory thresholds. Generates SARs automatically.",
    badge: "V3" as const,
    tools: ["Fraud Signal API", "Policy Engine", "Audit Trail"],
    status: "inactive" as const,
  },
];

export const API_TOOLS = [
  {
    id: "invoice-parser",
    name: "Invoice Parser API",
    endpoint: "POST /v1/parse/invoice",
    description: "Extracts structured data from invoice PDFs using Claude Vision. Returns vendor, amount, line items, due date, and PO reference with confidence scores.",
    useCases: [
      "Automated accounts payable processing",
      "Supplier invoice intake",
      "Multi-format invoice ingestion (PDF, image, email)",
    ],
  },
  {
    id: "receipt-ocr",
    name: "Receipt OCR + Policy Check API",
    endpoint: "POST /v1/parse/receipt",
    description: "OCR-extracts receipt data and runs it through your policy engine in a single call. Returns structured data plus an approval decision.",
    useCases: [
      "Expense report automation",
      "Travel and entertainment policy enforcement",
      "Mobile receipt capture",
    ],
  },
  {
    id: "document-reconciliation",
    name: "Document Reconciliation API",
    endpoint: "POST /v1/reconcile",
    description: "Matches purchase orders against invoices and delivery notes. Returns match status, discrepancies, and recommended action.",
    useCases: [
      "Three-way PO matching",
      "Goods received note validation",
      "Dispute identification",
    ],
  },
  {
    id: "fraud-signal",
    name: "Fraud Signal API",
    endpoint: "POST /v1/fraud/score",
    description: "Returns a 0–100 fraud risk score for any financial transaction. Integrates Stripe Radar signals with your internal baseline.",
    useCases: [
      "Real-time payment screening",
      "Vendor payment fraud prevention",
      "Anomaly detection in expense claims",
    ],
  },
  {
    id: "contract-extraction",
    name: "Contract Data Extraction API",
    endpoint: "POST /v1/parse/contract",
    description: "Extracts key terms from contracts: parties, payment terms, SLAs, renewal dates, and penalty clauses.",
    useCases: [
      "Vendor contract management",
      "Renewal date tracking",
      "Automated obligations monitoring",
    ],
  },
];

export const INTEGRATIONS = {
  Accounting: ["Xero", "QuickBooks", "FreshBooks", "Sage"],
  Banking: ["Plaid", "TrueLayer", "Codat"],
  Payments: ["Stripe", "GoCardless", "Adyen"],
  ERP: ["NetSuite", "SAP", "Microsoft Dynamics"],
  CRM: ["Salesforce", "HubSpot"],
  Storage: ["Gmail", "Outlook", "Google Drive", "Dropbox"],
};

export const TERMINAL_LINES = [
  { timestamp: "09:14:32", text: "Invoice received — Acme Supplies Ltd", color: "text-brand-muted" },
  { timestamp: "09:14:33", text: "Parser API — extracted 6 fields — confidence: 0.97", color: "text-brand-text" },
  { timestamp: "09:14:33", text: "Policy check — £1,240 — approval required", color: "text-brand-warning" },
  { timestamp: "09:14:34", text: "Approval request sent → sarah@company.com", color: "text-brand-info" },
  { timestamp: "09:14:51", text: "Approved by Sarah Chen", color: "text-brand-green" },
  { timestamp: "09:14:52", text: "Bill created in Xero — INV-2026-0041", color: "text-brand-text" },
  { timestamp: "09:14:52", text: "Payment scheduled — 2026-06-15", color: "text-brand-text" },
  { timestamp: "09:14:52", text: "Audit log written ✓", color: "text-brand-green" },
];

export const NAV_LINKS = [
  { label: "How It Works", href: "/how-it-works" },
  { label: "Workers", href: "/workers" },
  { label: "API Tools", href: "/api-tools" },
  { label: "Pricing", href: "/pricing" },
  { label: "Dashboard Demo", href: "/dashboard" },
];

export const HOW_IT_WORKS_STEPS = [
  {
    number: "01",
    title: "Connect Your Tools",
    description: "OAuth into Xero, QuickBooks, Plaid, and Stripe in under 5 minutes.",
    detail: "Clendan never stores your credentials. All tokens are encrypted at rest and scoped to the minimum permissions required.",
  },
  {
    number: "02",
    title: "Deploy a Worker",
    description: "Select a pre-built AI worker and configure its autonomy level.",
    detail: "Set thresholds for auto-execution vs human approval. Every decision is policy-bound.",
  },
  {
    number: "03",
    title: "Set Your Policies",
    description: "Define approval thresholds, supplier allowlists, and spend limits.",
    detail: "The policy engine runs on every agent output before any action is taken. It cannot be bypassed.",
  },
  {
    number: "04",
    title: "Workers Execute",
    description: "AI workers receive events and execute tasks end-to-end.",
    detail: "Full execution trace logged in real time. Every step is observable.",
  },
  {
    number: "05",
    title: "Review & Approve",
    description: "Flagged items appear in your approval queue with full reasoning.",
    detail: "Approve or reject from Slack, email, or the dashboard. Approvals expire after a configurable TTL.",
  },
  {
    number: "06",
    title: "Monitor Everything",
    description: "Full audit trail for every action. Immutable, searchable, exportable.",
    detail: "Never UPDATE or DELETE an audit row. The ledger is the source of truth.",
  },
];
