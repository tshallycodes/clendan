# Clendan — Website Demo Tasks
# Claude Code Implementation Guide
# Version: 1.0 | Status: Demo / Visual Preview Only
# Purpose: Build a static visual demo of the Clendan website to preview
#          look and feel before actual backend development begins.
#          No real APIs, no real auth, no real database — all mock data.

---

## Project Overview

Clendan is an AI Financial Agent OS. The website demo should communicate:
- What Clendan is (execution infrastructure for autonomous finance)
- Who it is for (CFOs, Finance Managers, CTOs at SaaS/fintech companies)
- How it works (deploy AI workers, connect financial tools, execute autonomously)
- Why it is different (not a dashboard, not a chatbot — actual execution with audit trails)

---

## Brand

```
Name:         Clendan
Primary:      #00C853 (Electric Growth green)
Background:   #0a0a0f (near black)
Surface:      #111118
Border:       #1a2a1a
Text:         #e8f0e8
Muted text:   #4a6a4a
Danger:       #ff4d6d
Info:         #00a8cc
Font 1:       Syne (headings) — Google Fonts
Font 2:       IBM Plex Mono (body, code) — Google Fonts
Border radius: 4px (sharp but not harsh)
```

---

## Tech Stack for Demo

```
Framework:    Next.js 14 with App Router
Language:     TypeScript
Styling:      Tailwind CSS
Components:   shadcn/ui
Animation:    Framer Motion
Icons:        Lucide React
Charts:       Recharts (for dashboard mockup)
Fonts:        next/font with Google Fonts
```

---

## Setup Instructions

```bash
npx create-next-app@latest clendan-demo --typescript --tailwind --app
cd clendan-demo
npx shadcn-ui@latest init
npm install framer-motion lucide-react recharts
npm install @next/font
```

Configure tailwind.config.ts to include Clendan brand colors:

```js
colors: {
  brand: {
    green: '#00C853',
    bg: '#0a0a0f',
    surface: '#111118',
    border: '#1a2a1a',
    text: '#e8f0e8',
    muted: '#4a6a4a',
    danger: '#ff4d6d',
    info: '#00a8cc',
  }
}
```

---

## Pages to Build

### Page 1 — Landing Page (/)
### Page 2 — How It Works (/how-it-works)
### Page 3 — AI Workers (/workers)
### Page 4 — API Tools (/api-tools)
### Page 5 — Dashboard Demo (/dashboard)
### Page 6 — Pricing (/pricing)

---

## Page 1 — Landing Page (/)

### Section 1.1 — Navigation Bar
- Logo: square bracket with "C" inside, next to "CLENDAN" in Syne bold, uppercase, letter-spaced
- Nav links: How It Works, Workers, API Tools, Pricing, Dashboard Demo
- CTA button: "Request Access" — filled green, sharp corners
- Secondary CTA: "View Docs" — outlined
- Sticky on scroll with subtle border appearing on scroll
- Mobile: hamburger menu

### Section 1.2 — Hero
- Headline (large, Syne, 700 weight):
  "Your Finance Team,\nRunning on Autopilot"
- Sub-headline (IBM Plex Mono, muted):
  "Deploy AI workers that connect to your financial systems,\nexecute tasks autonomously, and produce full audit trails\nfor every action. Not a dashboard. Execution infrastructure."
- Two CTAs: "Deploy Your First Worker" (green filled) and "See How It Works" (ghost)
- Animated terminal window below CTAs showing a live-looking execution log:
  ```
  [09:14:32] Invoice received — Acme Supplies Ltd
  [09:14:33] Parser API — extracted 6 fields — confidence: 0.97
  [09:14:33] Policy check — £1,240 — approval required
  [09:14:34] Approval request sent → sarah@company.com
  [09:14:51] Approved by Sarah Chen
  [09:14:52] Bill created in Xero — INV-2026-0041
  [09:14:52] Payment scheduled — 2026-06-15
  [09:14:52] Audit log written ✓
  ```
  Lines should animate in one by one with a typing effect and blinking cursor
- Background: subtle animated grid pattern in very dark green, low opacity
- Below hero: logos strip — "Trusted integrations with" + Xero, QuickBooks, Plaid, Stripe, NetSuite, Salesforce logos (use text placeholders if SVGs unavailable)

### Section 1.3 — Problem Statement
- Three column cards showing the problem:
  - Card 1: "66% of AP teams still process invoices manually" — source: Ardent Partners 2025
  - Card 2: "50% of finance teams take 6+ days to close the books" — source: Ledge 2025
  - Card 3: "$6+ to process a single invoice manually" — source: industry average
- Each card: large stat in green, description below, source in muted text
- Section headline: "Finance Operations Are Broken"

### Section 1.4 — Solution Overview
- Three column feature cards:
  - "Deploy AI Workers" — icon, short description
  - "Connect Your Tools" — icon, short description  
  - "Execute With Full Audit" — icon, short description
- Each card should have a thin green left border accent

### Section 1.5 — How It Works (summary)
- Horizontal step-by-step flow: Connect → Configure → Execute → Monitor
- Each step has a number, title, and one-line description
- Connected by a dashed line between steps
- On mobile: vertical stack

### Section 1.6 — Worker Showcase
- Headline: "10 AI Workers. Every Finance Function Covered."
- Grid of worker cards (2 per row on desktop, 1 on mobile):
  - Invoice Processing Worker — MVP badge
  - AI Accountant Worker — MVP badge
  - Reconciliation Worker — V2 badge
  - Expense Control Worker — V2 badge
  - Collections Worker — V2 badge
  - Fraud Detection Worker — V2 badge
  - Treasury Worker — V2 badge
  - Revenue Recognition Worker — V2 badge
  - Credit Underwriting Worker — V3 badge
  - Compliance Worker — V3 badge
- Each card: worker name, one-line description, badge, tools list as small pills
- Hover: card lifts slightly, green border intensifies

### Section 1.7 — Standalone API Tools
- Headline: "5 Standalone APIs. Use Them Inside Clendan or On Their Own."
- Horizontal scroll on mobile, grid on desktop
- Cards for each API tool:
  - Invoice Parser API — POST /v1/parse/invoice
  - Receipt OCR + Policy Check API — POST /v1/parse/receipt
  - Document Reconciliation API — POST /v1/reconcile
  - Fraud Signal API — POST /v1/fraud/score
  - Contract Data Extraction API — POST /v1/parse/contract
- Each card shows the endpoint in monospace, description, and "Try It" ghost button

### Section 1.8 — Integration Strip
- Headline: "Plugs Into Your Existing Stack"
- Grid of integration logos/names with category labels:
  - Accounting: Xero, QuickBooks, FreshBooks, Sage
  - Banking: Plaid, TrueLayer, Codat
  - Payments: Stripe, GoCardless, Adyen
  - ERP: NetSuite, SAP, Microsoft Dynamics
  - CRM: Salesforce, HubSpot
  - Storage: Gmail, Outlook, Google Drive, Dropbox

### Section 1.9 — Testimonial / Social Proof Placeholder
- Three mock testimonial cards with placeholder names and companies
- Quote about saving time on invoice processing or month-end close
- Note in code comment: "REPLACE WITH REAL TESTIMONIALS"

### Section 1.10 — CTA Banner
- Full-width dark green tinted section
- Headline: "Ready to Automate Your Finance Stack?"
- Sub: "Deploy your first AI worker in under 10 minutes."
- Button: "Request Early Access"

### Section 1.11 — Footer
- Logo + one-line description
- Links: Product (Workers, API Tools, Pricing, Changelog), Company (About, Blog, Careers), Developers (Docs, API Reference, Status), Legal (Privacy, Terms, Security)
- Bottom bar: copyright, "Built for finance teams that move fast"
- Social icons: GitHub, LinkedIn, Twitter/X

---

## Page 2 — How It Works (/how-it-works)

### Layout
- Step-by-step vertical scroll journey
- Each step takes up most of the viewport height
- Sticky progress indicator on the left showing which step the user is on

### Steps to Show
1. **Connect Your Tools** — show the OAuth connection flow mockup for Xero/QuickBooks
2. **Deploy a Worker** — show the worker configuration UI with role, tools, autonomy level
3. **Set Your Policies** — show the policy engine UI with approval thresholds and rules
4. **Workers Execute** — show the animated execution log (same terminal component as hero)
5. **Review & Approve** — show the approval queue UI
6. **Monitor Everything** — show the dashboard with audit trail

---

## Page 3 — AI Workers (/workers)

### Layout
- Hero section with headline and description
- Filter tabs: All Workers / MVP / V2 / V3
- Grid of detailed worker cards
- Each card expands on click to show:
  - Full description
  - Responsibilities list
  - Tools it uses
  - Sample output
  - Which integrations it connects to

---

## Page 4 — API Tools (/api-tools)

### Layout
- Hero: "5 APIs. Plug Into Any Stack."
- For each API tool, a full section with:
  - Endpoint URL
  - Description
  - Sample request (JSON code block, dark themed)
  - Sample response (JSON code block)
  - Use cases list
  - "View Docs" button (placeholder link)
- Code blocks should have syntax highlighting using a simple CSS approach
- Language tabs: Python / Node.js / cURL

### Sample Code Blocks to Include

**Invoice Parser API — Python:**
```python
import requests

response = requests.post(
    "https://api.clendan.com/v1/parse/invoice",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    files={"file": open("invoice.pdf", "rb")}
)

data = response.json()
print(data["vendor"])       # "Acme Supplies Ltd"
print(data["total_amount"]) # 1240.00
print(data["confidence"])   # 0.97
```

**Invoice Parser API — Node.js:**
```javascript
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('invoice.pdf'));

const response = await fetch('https://api.clendan.com/v1/parse/invoice', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer YOUR_API_KEY', ...form.getHeaders() },
  body: form
});

const data = await response.json();
```

Include similar patterns for the other 4 APIs.

---

## Page 5 — Dashboard Demo (/dashboard)

This is the most important page. It should look like a real product dashboard with mock data.

### Layout
- Full-screen dashboard layout
- Left sidebar navigation
- Top bar with Clendan logo, search, notifications bell, user avatar

### Sidebar Navigation Items
- Overview (home icon)
- Workers (bot icon)
- Approvals (check icon) — show badge with number 3
- Audit Trail (list icon)
- Integrations (plug icon)
- API Keys (key icon)
- Settings (gear icon)

### Main Content — Overview Tab (default view)

**Top stats row (4 cards):**
- Invoices Processed Today: 14 (+3 from yesterday)
- Hours Saved This Month: 47.5 hrs
- Pending Approvals: 3
- Fraud Flags: 1

**Execution Activity Chart:**
- Line chart using Recharts
- X axis: last 7 days
- Y axis: number of executions
- Two lines: auto-executed (green) vs required-approval (blue)
- Mock data showing realistic daily volumes (15-40 range)

**Recent Executions Table:**
Columns: Time | Worker | Action | Amount | Status | View
Mock rows:
- 09:14 | Invoice Processing | Bill created in Xero | £1,240 | ✓ Auto | →
- 09:02 | AI Accountant | Transaction categorised | £340 | ✓ Auto | →
- 08:55 | Invoice Processing | Approval requested | £3,800 | ⏳ Pending | →
- 08:41 | Fraud Detection | Transaction flagged | £12,400 | ⚠ Flagged | →
- 08:30 | AI Accountant | Reconciliation complete | — | ✓ Auto | →

**Active Workers Panel:**
- Show 2 active workers with green pulse indicator
- Invoice Processing Worker — running — processed 14 today
- AI Accountant Worker — running — last action 2 mins ago

### Approvals Tab

List of pending approvals:
- Each row: invoice vendor, amount, submitted by worker, time waiting, Approve / Reject buttons
- Mock data: 3 pending approvals
- Clicking Approve shows a success toast notification

### Audit Trail Tab

- Full log table with filters: All / Auto-Executed / Approved / Rejected / Flagged
- Columns: Timestamp | Worker | Action | Decision | Reasoning | Trace ID
- Clicking a row expands to show full reasoning trace:
  ```
  Decision: APPROVE
  Worker: Invoice Processing Worker v1.2
  Input: invoice.pdf — Acme Supplies Ltd — £1,240
  Policy check: amount £1,240 < threshold £5,000 ✓
  Supplier verified: Acme Supplies Ltd in approved list ✓
  PO match: PO-2026-0089 matched ✓
  Confidence: 0.97
  Action: Bill created in Xero — ID: BILL-4421
  Duration: 1.8 seconds
  ```

---

## Page 6 — Pricing (/pricing)

### Three Tiers

**Starter — £299/month**
- 2 AI workers
- 500 executions/month
- QuickBooks + Xero integrations
- Basic policy engine
- Email support
- Audit trail: 30 days

**Growth — £799/month** (highlight as most popular)
- 5 AI workers
- 5,000 executions/month
- All integrations
- Advanced policy engine
- Standalone API access (10,000 calls/month)
- Priority support
- Audit trail: 1 year

**Enterprise — Custom**
- Unlimited workers
- Unlimited executions
- Custom integrations
- SLA guarantee
- Dedicated support
- SOC 2 compliance
- Audit trail: unlimited
- On-premise option

### Below Pricing Table
- FAQ section with 5 questions:
  1. What counts as an execution?
  2. Can I build my own workers?
  3. How does the audit trail work?
  4. Is my financial data encrypted?
  5. Do you offer a free trial?
- Each question expands on click (accordion)

---

## Shared Components to Build

### TerminalWindow
- Dark window with macOS-style traffic light dots (red/yellow/green circles)
- Window title bar with monospace title
- Content area with line-by-line animated text
- Blinking cursor at end
- Optional: typewriter animation for each new line

### WorkerCard
- Props: name, description, badge (MVP/V2/V3), tools[], status
- Hover effect: translate Y -2px, border color to green
- Badge colors: MVP = green, V2 = blue, V3 = muted

### ApiCodeBlock
- Props: language, code string
- Language tabs: Python / Node.js / cURL
- Copy button top right
- Syntax: keywords in green, strings in yellow, comments in muted

### StatCard
- Props: value, label, change, changeDirection
- Large value in Syne font
- Green up arrow or red down arrow for change

### AuditTraceExpand
- Expandable row component
- Shows structured trace data in monospace
- Key-value pairs with color coding

### ToastNotification
- Appears bottom right
- Green for success, red for error
- Auto-dismisses after 3 seconds

---

## Animations

- Hero terminal: lines animate in 300ms apart, blinking cursor
- Worker cards: staggered fade-up on scroll into view (Framer Motion)
- Stat cards: count up animation when they enter viewport
- Dashboard chart: animate drawing on load
- Navigation: smooth underline slide on hover
- Page transitions: subtle fade between pages

---

## Responsive Breakpoints

- Mobile: < 640px
- Tablet: 640px – 1024px
- Desktop: > 1024px

Every section must be fully responsive. Test each page at all three sizes.

---

## File Structure

```
clendan-demo/
├── app/
│   ├── layout.tsx              # Root layout with fonts and global styles
│   ├── page.tsx                # Landing page
│   ├── how-it-works/
│   │   └── page.tsx
│   ├── workers/
│   │   └── page.tsx
│   ├── api-tools/
│   │   └── page.tsx
│   ├── dashboard/
│   │   └── page.tsx
│   └── pricing/
│       └── page.tsx
├── components/
│   ├── layout/
│   │   ├── Navbar.tsx
│   │   ├── Footer.tsx
│   │   └── Sidebar.tsx
│   ├── ui/
│   │   ├── TerminalWindow.tsx
│   │   ├── WorkerCard.tsx
│   │   ├── ApiCodeBlock.tsx
│   │   ├── StatCard.tsx
│   │   ├── AuditTraceExpand.tsx
│   │   └── ToastNotification.tsx
│   ├── sections/
│   │   ├── Hero.tsx
│   │   ├── ProblemStatement.tsx
│   │   ├── WorkerShowcase.tsx
│   │   ├── ApiToolsStrip.tsx
│   │   ├── IntegrationStrip.tsx
│   │   └── CtaBanner.tsx
│   └── dashboard/
│       ├── OverviewTab.tsx
│       ├── ApprovalsTab.tsx
│       ├── AuditTrailTab.tsx
│       └── ExecutionChart.tsx
├── lib/
│   ├── mock-data.ts            # All mock data in one place
│   ├── constants.ts            # Brand colors, worker list, API tools
│   └── utils.ts
├── public/
│   └── fonts/
├── tailwind.config.ts
├── next.config.js
└── tsconfig.json
```

---

## Mock Data (lib/mock-data.ts)

Define all mock data here so it is easy to replace with real API calls later:

```typescript
export const MOCK_EXECUTIONS = [
  {
    id: 'exec-001',
    time: '09:14:32',
    worker: 'Invoice Processing Worker',
    action: 'Bill created in Xero',
    amount: 1240,
    currency: 'GBP',
    status: 'auto',
    traceId: 'trace-a1b2c3'
  },
  // ... more rows
]

export const MOCK_PENDING_APPROVALS = [
  {
    id: 'appr-001',
    vendor: 'CloudStack Ltd',
    amount: 3800,
    currency: 'GBP',
    submittedBy: 'Invoice Processing Worker',
    waitingMins: 24,
    invoiceRef: 'INV-2026-0044'
  },
  // ... more rows
]

export const MOCK_CHART_DATA = [
  { day: 'Mon', autoExecuted: 32, approvalRequired: 4 },
  { day: 'Tue', autoExecuted: 28, approvalRequired: 6 },
  { day: 'Wed', autoExecuted: 41, approvalRequired: 3 },
  { day: 'Thu', autoExecuted: 19, approvalRequired: 8 },
  { day: 'Fri', autoExecuted: 37, approvalRequired: 5 },
  { day: 'Sat', autoExecuted: 12, approvalRequired: 1 },
  { day: 'Sun', autoExecuted: 8, approvalRequired: 0 },
]
```

---

## Important Notes for Claude Code

1. This is a DEMO only — no backend, no real auth, no real API calls. All data is from mock-data.ts.

2. Do not install unnecessary packages. Stick to the list above.

3. Every component must use Clendan brand colors from tailwind.config.ts — no hardcoded hex values in components.

4. The dashboard page (/dashboard) should be the most polished page — this is what investors and design partners will see first.

5. Add a visible "DEMO MODE" banner in yellow at the top of the dashboard page so it is clear this is not production.

6. All forms and buttons should have hover and active states.

7. Code must be clean TypeScript — no `any` types, proper interfaces for all data.

8. Add a README.md explaining how to run the project locally.

9. After building, run `npm run build` to confirm no TypeScript or build errors before finishing.

10. The terminal animation component is the most important visual — spend extra time making it look polished and realistic.
