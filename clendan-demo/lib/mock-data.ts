export interface Execution {
  id: string;
  time: string;
  worker: string;
  action: string;
  amount: number | null;
  currency: string;
  status: "auto" | "pending" | "flagged" | "rejected";
  traceId: string;
}

export interface PendingApproval {
  id: string;
  vendor: string;
  amount: number;
  currency: string;
  submittedBy: string;
  waitingMins: number;
  invoiceRef: string;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  worker: string;
  action: string;
  decision: "APPROVE" | "REJECT" | "FLAG" | "AUTO";
  reasoning: string;
  traceId: string;
  amount: number | null;
  currency: string;
  fullTrace: string;
}

export interface ChartDataPoint {
  day: string;
  autoExecuted: number;
  approvalRequired: number;
}

export const MOCK_EXECUTIONS: Execution[] = [
  {
    id: "exec-001",
    time: "09:14:32",
    worker: "Invoice Processing Worker",
    action: "Bill created in Xero",
    amount: 1240,
    currency: "GBP",
    status: "auto",
    traceId: "trace-a1b2c3",
  },
  {
    id: "exec-002",
    time: "09:02:11",
    worker: "AI Accountant Worker",
    action: "Transaction categorised",
    amount: 340,
    currency: "GBP",
    status: "auto",
    traceId: "trace-d4e5f6",
  },
  {
    id: "exec-003",
    time: "08:55:44",
    worker: "Invoice Processing Worker",
    action: "Approval requested",
    amount: 3800,
    currency: "GBP",
    status: "pending",
    traceId: "trace-g7h8i9",
  },
  {
    id: "exec-004",
    time: "08:41:20",
    worker: "Fraud Detection Worker",
    action: "Transaction flagged",
    amount: 12400,
    currency: "GBP",
    status: "flagged",
    traceId: "trace-j0k1l2",
  },
  {
    id: "exec-005",
    time: "08:30:05",
    worker: "AI Accountant Worker",
    action: "Reconciliation complete",
    amount: null,
    currency: "GBP",
    status: "auto",
    traceId: "trace-m3n4o5",
  },
];

export const MOCK_PENDING_APPROVALS: PendingApproval[] = [
  {
    id: "appr-001",
    vendor: "CloudStack Ltd",
    amount: 3800,
    currency: "GBP",
    submittedBy: "Invoice Processing Worker",
    waitingMins: 24,
    invoiceRef: "INV-2026-0044",
  },
  {
    id: "appr-002",
    vendor: "DataBridge Systems",
    amount: 7250,
    currency: "GBP",
    submittedBy: "Invoice Processing Worker",
    waitingMins: 87,
    invoiceRef: "INV-2026-0042",
  },
  {
    id: "appr-003",
    vendor: "Meridian Consulting",
    amount: 15000,
    currency: "GBP",
    submittedBy: "Invoice Processing Worker",
    waitingMins: 142,
    invoiceRef: "INV-2026-0039",
  },
];

export const MOCK_AUDIT_ENTRIES: AuditEntry[] = [
  {
    id: "audit-001",
    timestamp: "2026-05-22 09:14:52",
    worker: "Invoice Processing Worker",
    action: "Bill created in Xero",
    decision: "AUTO",
    reasoning: "Amount £1,240 below auto-approve threshold £5,000. Supplier verified.",
    traceId: "trace-a1b2c3",
    amount: 1240,
    currency: "GBP",
    fullTrace: `Decision: AUTO-APPROVE
Worker: Invoice Processing Worker v1.2
Input: invoice.pdf — Acme Supplies Ltd — £1,240
Policy check: amount £1,240 < threshold £5,000 ✓
Supplier verified: Acme Supplies Ltd in approved list ✓
PO match: PO-2026-0089 matched ✓
Confidence: 0.97
Action: Bill created in Xero — ID: BILL-4421
Duration: 1.8 seconds`,
  },
  {
    id: "audit-002",
    timestamp: "2026-05-22 09:02:11",
    worker: "AI Accountant Worker",
    action: "Transaction categorised",
    decision: "AUTO",
    reasoning: "Transaction pattern matches SaaS subscription category with 0.94 confidence.",
    traceId: "trace-d4e5f6",
    amount: 340,
    currency: "GBP",
    fullTrace: `Decision: AUTO-CATEGORISE
Worker: AI Accountant Worker v1.0
Input: transaction — Stripe charge — £340
Category inference: SaaS subscription — confidence 0.94 ✓
Merchant: Vercel Inc — recognised ✓
Action: Categorised as 'Software & Subscriptions'
Duration: 0.4 seconds`,
  },
  {
    id: "audit-003",
    timestamp: "2026-05-22 08:55:44",
    worker: "Invoice Processing Worker",
    action: "Approval requested",
    decision: "FLAG",
    reasoning: "Amount £3,800 exceeds auto-approve threshold. Routed to approval queue.",
    traceId: "trace-g7h8i9",
    amount: 3800,
    currency: "GBP",
    fullTrace: `Decision: REQUIRES-APPROVAL
Worker: Invoice Processing Worker v1.2
Input: invoice.pdf — CloudStack Ltd — £3,800
Policy check: amount £3,800 > threshold £2,000 — approval required
Supplier verified: CloudStack Ltd in approved list ✓
Action: Approval request sent to finance@company.com
Duration: 2.1 seconds`,
  },
  {
    id: "audit-004",
    timestamp: "2026-05-22 08:41:20",
    worker: "Fraud Detection Worker",
    action: "Transaction blocked",
    decision: "REJECT",
    reasoning: "Fraud score 94/100. New vendor. Unusual payment time. Amount 8x baseline.",
    traceId: "trace-j0k1l2",
    amount: 12400,
    currency: "GBP",
    fullTrace: `Decision: BLOCK
Worker: Fraud Detection Worker v1.1
Input: payment — Unknown Vendor LLC — £12,400
Fraud score: 94/100 — exceeds threshold 75 ✗
New vendor: no prior transactions ✗
Payment time: 03:41 UTC — outside normal window ✗
Amount: 8.3x 90-day average ✗
Action: Transaction blocked. Finance team alerted via Slack.
Duration: 0.9 seconds`,
  },
  {
    id: "audit-005",
    timestamp: "2026-05-22 08:30:05",
    worker: "AI Accountant Worker",
    action: "Reconciliation complete",
    decision: "AUTO",
    reasoning: "All 47 transactions matched. Zero discrepancies detected.",
    traceId: "trace-m3n4o5",
    amount: null,
    currency: "GBP",
    fullTrace: `Decision: RECONCILIATION-COMPLETE
Worker: AI Accountant Worker v1.0
Scope: Daily reconciliation — May 22 2026
Transactions checked: 47
Matched: 47
Unmatched: 0
Discrepancies: 0
Action: Reconciliation report written to audit log
Duration: 4.2 seconds`,
  },
];

export const MOCK_CHART_DATA: ChartDataPoint[] = [
  { day: "Mon", autoExecuted: 32, approvalRequired: 4 },
  { day: "Tue", autoExecuted: 28, approvalRequired: 6 },
  { day: "Wed", autoExecuted: 41, approvalRequired: 3 },
  { day: "Thu", autoExecuted: 19, approvalRequired: 8 },
  { day: "Fri", autoExecuted: 37, approvalRequired: 5 },
  { day: "Sat", autoExecuted: 12, approvalRequired: 1 },
  { day: "Sun", autoExecuted: 8, approvalRequired: 0 },
];
