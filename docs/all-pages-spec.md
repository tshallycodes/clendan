# Clendan — Full Website Pages Content Specification
# All 32 pages — marketing, auth, dashboard, legal, error

---

## MARKETING PAGES (Public)

---

### 1. / (Landing Page)

**Purpose:** Convert visitors into signups. Communicate what Clendan is in under 10 seconds.

**Sections:**

**Navbar**
- Logo: square bracket mark + "CLENDAN" in Syne bold uppercase
- Links: How It Works, Workers, API Tools, Pricing
- CTA: "Request Access" (green filled) + "View Docs" (ghost)
- Sticky on scroll — subtle border appears on scroll
- Mobile: hamburger menu

**Hero**
- Headline: "Your Finance Team, Running on Autopilot"
- Subheadline: "Deploy AI workers that connect to your financial systems, execute tasks autonomously, and produce full audit trails for every action. Not a dashboard. Execution infrastructure."
- CTAs: "Deploy Your First Worker" (green) + "See How It Works" (ghost)
- Animated terminal window showing live execution log (lines animate in one by one)
- Background: subtle animated dark grid pattern

**Social Proof Strip**
- "Trusted integrations with:" + Xero, QuickBooks, Plaid, Stripe, NetSuite, Salesforce

**Problem Statement**
- Headline: "Finance Operations Are Broken"
- Three stat cards:
  - "66% of AP teams still process invoices manually" — Ardent Partners 2025
  - "50% of finance teams take 6+ days to close the books" — Ledge 2025
  - "$6+ to process a single invoice manually" — industry average

**Solution Overview**
- Three feature cards:
  - Deploy AI Workers
  - Connect Your Tools
  - Execute With Full Audit Trail

**How It Works Summary**
- Four steps: Connect → Configure → Execute → Monitor
- Horizontal flow connected by dashed line
- Mobile: vertical stack

**Worker Showcase**
- Headline: "10 AI Workers. Every Finance Function Covered."
- Grid of worker cards with MVP/V2/V3 badges

**Standalone API Tools Strip**
- Headline: "5 Standalone APIs. Use Them Inside Clendan or On Their Own."
- Cards with endpoint, description, "Try It" ghost button

**Integration Strip**
- Headline: "Plugs Into Your Existing Stack"
- Grouped by category: Accounting, Banking, Payments, ERP, CRM, Storage

**Testimonials**
- Three cards — placeholder until real testimonials available
- Note in code: REPLACE WITH REAL TESTIMONIALS

**CTA Banner**
- "Ready to Automate Your Finance Stack?"
- "Deploy your first AI worker in under 10 minutes."
- "Request Early Access" button

**Footer**
- Logo + one-line description
- Links: Product, Company, Developers, Legal
- Social: GitHub, LinkedIn, Twitter/X

---

### 2. /how-it-works

**Purpose:** Walk visitors through the full Clendan workflow step by step.

**Sections:**

**Hero**
- Headline: "From Invoice to Payment. Zero Manual Work."
- Subheadline: "Here's exactly how Clendan handles your financial operations end to end."

**Step-by-Step Journey (full viewport height per step, sticky progress indicator on left)**
1. **Connect Your Tools** — OAuth flow mockup for Xero/QuickBooks. Copy: "Connect your existing financial systems in one click. No engineering required."
2. **Deploy a Worker** — Worker configuration UI mockup. Copy: "Select a worker, set its role, define its autonomy level, and connect its tools."
3. **Set Your Policies** — Policy engine UI mockup. Copy: "Define exactly when workers act autonomously and when they ask for your approval."
4. **Workers Execute** — Animated terminal execution log. Copy: "Workers run continuously. Every invoice, every transaction, every decision — handled."
5. **Review & Approve** — Approval queue UI mockup. Copy: "For anything above your threshold, workers pause and route to your queue. One click to approve."
6. **Full Audit Trail** — Audit trail UI mockup. Copy: "Every action logged. Every decision explained. Ready for auditors whenever you need it."

**Results Section**
- Three outcome metrics:
  - "Invoice processing cost: $6 → under $1"
  - "Month-end close: 6 days → 1–2 days"
  - "AP team hours recovered: 10+ hrs/week"

**CTA**
- "Start Automating in 10 Minutes" → sign up link

---

### 3. /workers

**Purpose:** Full catalogue of all 10 AI workers. Helps buyers understand what they're deploying.

**Sections:**

**Hero**
- Headline: "10 AI Workers. Built for Every Finance Function."
- Subheadline: "Each worker is a specialised sub-agent with a defined role, tools, and policy rules. Deploy one or deploy all."

**Filter Tabs**
- All | MVP (available now) | V2 (coming soon) | V3 (roadmap)

**Worker Cards Grid (2 per row desktop, 1 mobile)**
Each card contains:
- Worker name
- Phase badge (MVP / V2 / V3)
- One-line description
- Responsibilities list (bullet points)
- Tools it uses (pill list)
- Sample output description
- "Learn more" expands card inline
- "Deploy" button (MVP only, others greyed)

**Workers to include:**
1. Invoice Processing Worker — MVP
2. AI Accountant Worker — MVP
3. Reconciliation Worker — V2
4. Expense Control Worker — V2
5. Collections Worker — V2
6. Fraud Detection Worker — V2
7. Treasury Worker — V2
8. Revenue Recognition Worker — V2
9. Credit Underwriting Worker — V3
10. Compliance Worker — V3
11. Financial Orchestrator (Master Agent) — V3 — explain it coordinates all others

**Architecture Callout**
- Short explanation of master-subagent model
- Simple diagram: Orchestrator → Workers
- Copy: "Workers never call each other. All coordination flows through the Orchestrator."

**CTA**
- "Start with the Invoice Processing Worker — deploy in under 5 minutes"

---

### 4. /api-tools

**Purpose:** Technical buyers who want to use Clendan's APIs standalone, not the full platform.

**Sections:**

**Hero**
- Headline: "5 APIs. Plug Into Any Stack."
- Subheadline: "Use them inside Clendan or call them directly from your own systems. JSON in, JSON out. No configuration."

**Language Tabs (global, switches all code blocks)**
- Python | Node.js | cURL

**Per-API Section (one full section per tool):**

**Invoice Parser API**
- Endpoint: `POST /v1/parse/invoice`
- Description: Takes any invoice format, returns structured JSON
- Input: PDF/PNG/JPG/TIFF file upload
- Output fields: vendor, invoice_number, line_items, amount_minor, currency, due_date, vat, po_number, confidence
- Sample request code block (Python/Node/cURL)
- Sample response JSON block
- Use cases: AP automation, ERP ingestion, supplier management
- "View full docs →" link

**Receipt OCR + Policy Check API**
- Endpoint: `POST /v1/parse/receipt`
- Description: Extracts receipt data and validates against expense policy
- Input: receipt image + policy_rules object
- Output: extracted data + approved/rejected decision + reason
- Code blocks + sample response
- Use cases: expense management, travel reimbursement, audit prep

**Document Reconciliation API**
- Endpoint: `POST /v1/reconcile`
- Description: Takes two financial datasets, returns matched/unmatched/flagged rows
- Input: two arrays of financial records
- Output: matched[], unmatched[], flagged[] with confidence scores
- Code blocks + sample response
- Use cases: month-end close, bank reconciliation, multi-system sync

**Fraud Signal API**
- Endpoint: `POST /v1/fraud/score`
- Description: Returns risk score and reasoning for a transaction or batch
- Input: transaction object or array
- Output: risk_score (0–1), risk_level (low/medium/high), signals[], reasoning
- Code blocks + sample response
- Use cases: payment screening, lending risk, real-time transaction monitoring

**Contract Data Extraction API**
- Endpoint: `POST /v1/parse/contract`
- Description: Extracts structured data from contract PDFs
- Input: contract PDF
- Output: counterparty, payment_terms, renewal_date, obligations[], amounts[], governing_law
- Code blocks + sample response
- Use cases: revenue recognition, procurement, legal ops

**Pricing Note**
- "Standalone API access included in Growth and Enterprise plans"
- Link to pricing page

---

### 5. /integrations

**Purpose:** Show every system Clendan connects to. Builds trust with buyers evaluating fit.

**Sections:**

**Hero**
- Headline: "Clendan Works Where You Already Work"
- Subheadline: "Connect your existing financial stack in one click. No engineering required for standard integrations."

**Integration Categories (tabs or sections):**

**Accounting**
- Xero, QuickBooks, FreshBooks, Sage, Wave
- Each: logo, name, what data it syncs, connection method (OAuth), status (Available/Coming Soon)

**Banking & Open Banking**
- Plaid, TrueLayer, Codat, Nordigen
- Each: logo, name, what it provides (bank feeds, balances, transactions)

**Payments**
- Stripe, GoCardless, Adyen, Wise, PayPal
- Each: logo, name, what data flows in/out

**ERP**
- NetSuite, SAP, Microsoft Dynamics 365, Sage Intacct
- Note: Enterprise tier required for SAP and Dynamics

**CRM**
- Salesforce, HubSpot
- Used by: Collections Worker, Revenue Recognition Worker

**Document & Email**
- Gmail, Outlook, Google Drive, Dropbox, OneDrive
- Used for invoice ingestion

**How Integrations Work**
- Three steps: Connect (OAuth) → Sync (initial data pull) → Live (continuous)
- Security note: "Credentials encrypted at rest. Never stored in plaintext. Full permission scoping."

**Custom Integration**
- "Need a custom integration? Contact us." → link to contact/enterprise form

---

### 6. /pricing

**Purpose:** Convert evaluation to purchase decision.

**Sections:**

**Hero**
- Headline: "Simple, Transparent Pricing"
- Toggle: Monthly / Annual (annual = 2 months free)

**Three Tier Cards:**

**Starter — £299/month**
- 2 AI workers
- 500 executions/month
- QuickBooks + Xero integrations only
- Basic policy engine
- Approval queue
- Audit trail: 30 days retention
- Email support
- Best for: Small teams, single finance function

**Growth — £799/month** (highlight as Most Popular)
- 5 AI workers
- 5,000 executions/month
- All integrations
- Advanced policy engine
- Standalone API access (10,000 calls/month)
- Human approval API
- Explainability API
- Audit trail: 1 year retention
- Priority support
- PostHog analytics dashboard
- Best for: Growing SaaS and fintech teams

**Enterprise — Custom pricing**
- Unlimited workers
- Unlimited executions
- Custom integrations
- SLA guarantee (99.9% uptime)
- Dedicated onboarding
- Dedicated support manager
- SOC 2 Type II compliance
- Audit trail: unlimited retention
- On-premise deployment option
- Custom contract and invoicing
- Best for: Large finance teams, regulated industries
- CTA: "Talk to Sales" → contact form

**Feature Comparison Table**
- Full table comparing all three tiers across every feature

**FAQ Accordion (5 questions)**
1. What counts as an execution?
2. Can I build my own custom workers?
3. How does the audit trail work?
4. Is my financial data encrypted?
5. Can I switch plans at any time?

**CTA**
- "Start with a 14-day free trial — no credit card required"

---

### 7. /about

**Purpose:** Build trust with buyers doing due diligence.

**Sections:**

**Hero**
- Headline: "Finance Teams Shouldn't Be Doing Repetitive Work"
- Short founding story: why Clendan exists, what problem drove it

**Mission Statement**
- "Our mission: give every finance team the autonomous infrastructure to focus on decisions, not execution."

**Team Section**
- Founder cards: name, role, short bio, LinkedIn link
- Placeholder until real photos available

**What We're Building**
- Short version of the vision: from invoice processing wedge to full finance OS
- Timeline / roadmap visual

**Investors / Backers** (placeholder section)
- "Backed by [investors]" — leave blank until applicable
- Or: remove entirely until funded

**Contact**
- hello@clendan.com
- LinkedIn, Twitter/X links

---

### 8. /blog

**Purpose:** SEO, thought leadership, content marketing for finance and fintech buyers.

**Sections:**

**Hero**
- Headline: "Finance Automation Insights"
- Subheadline: "Practical guides, product updates, and research for finance teams."

**Featured Post**
- Large card: title, excerpt, date, category, "Read more →"

**Post Grid**
- Category filters: All | Product | Guides | Research | Updates
- Card per post: title, excerpt, date, read time, category badge, author

**Suggested Categories for First Posts:**
- "Why 66% of AP teams are still manually processing invoices in 2025"
- "How to reduce month-end close from 6 days to 2"
- "API-first vs closed SaaS: why it matters for finance automation"
- "What is an AI financial agent and how is it different from automation?"
- "Invoice processing cost: how we got it under $1"

**Individual Blog Post Page (/blog/[slug])**
- Title, date, author, read time
- Body content (MDX)
- Table of contents sidebar
- Related posts at bottom
- CTA: "See how Clendan automates this →"

---

### 9. /changelog

**Purpose:** Show product is alive and moving. Builds trust with technical buyers.

**Sections:**

**Hero**
- Headline: "What's New in Clendan"
- Subheadline: "Every update, fix, and new feature — in order."

**Change Entries (newest first)**
- Date badge
- Version number (e.g. v1.2.0)
- Category tag: New Feature / Improvement / Fix / Integration
- Title
- Description (2–5 lines)
- Screenshot or code snippet where relevant

**Subscribe to Updates**
- Email input: "Get notified of new releases"

---

### 10. /security

**Purpose:** Unblock procurement and legal reviews at target companies.

**Sections:**

**Hero**
- Headline: "Security Built for Financial Infrastructure"
- Subheadline: "Every decision Clendan makes is auditable. Every credential is encrypted. Every tenant is isolated."

**Security Principles**
- Four cards:
  - Data Encryption: at rest (AES-256) + in transit (TLS 1.3)
  - Tenant Isolation: row-level security, no cross-tenant data access
  - Audit Immutability: append-only audit logs, never deleted
  - Access Controls: role-based, Clerk-verified, least-privilege

**SOC 2 Roadmap**
- Current status: "SOC 2 Type II in progress — target Q4 2026"
- What it covers
- "Contact us for current security documentation"

**Data Handling**
- What data Clendan stores
- Data residency (UK/EU)
- Retention policies
- Right to erasure process

**Vulnerability Disclosure**
- Responsible disclosure policy
- Contact: security@clendan.com
- Response SLA: 48 hours

**Penetration Testing**
- "Annual third-party penetration testing" — placeholder until completed

---

### 11. /docs

**Purpose:** Redirect to Mintlify documentation.

- Simple redirect: `window.location.href = 'https://docs.clendan.com'`
- Or a landing page with links to key doc sections while Mintlify is being set up

---

## AUTHENTICATION PAGES

---

### 12. /sign-in

**Purpose:** Clerk-powered sign in.

- Clendan logo centred at top
- Clerk `<SignIn />` component
- "Don't have an account? Sign up →" link
- Dark background matching dashboard theme
- No navbar, no footer — clean focused layout

---

### 13. /sign-up

**Purpose:** Clerk-powered sign up.

- Clendan logo centred at top
- Clerk `<SignUp />` component
- "Already have an account? Sign in →" link
- Dark background matching dashboard theme
- No navbar, no footer

---

### 14. /onboarding

**Purpose:** Post-signup setup. Collects company context, connects first integration, deploys first worker.
**Protected:** requires auth. Redirect here after sign-up if onboarding not complete.

**Step 1 — Company Details**
- Company name (required)
- Industry dropdown (SaaS / Fintech / E-commerce / Professional Services / Other)
- Company size dropdown (1–10 / 11–50 / 51–200 / 200+)
- Primary use case (Invoice Processing / Reconciliation / Expense Management / Other)
- Next button

**Step 2 — Connect Your First Integration**
- Headline: "Connect your accounting software to get started"
- Xero and QuickBooks as primary options (OAuth buttons)
- "Skip for now — I'll connect later" option
- Note: "You can add more integrations after setup"

**Step 3 — Deploy Your First Worker**
- Headline: "Deploy your Invoice Processing Worker"
- Pre-selected: Invoice Processing Worker (only option in MVP)
- Autonomy level selector with explanation:
  - Auto: processes under your threshold without approval
  - Approve: always asks before acting
  - Suggest: recommends actions, you execute manually
- Approval threshold input: "Auto-approve invoices under £ [input]"
- "Deploy Worker" button

**Step 4 — Complete**
- "You're ready. Your first worker is live."
- "Go to Dashboard" button
- Confetti animation (optional, subtle)

**Progress indicator** across all steps (1 of 4, 2 of 4 etc.)

---

## LEGAL PAGES

---

### 15. /privacy

**Purpose:** GDPR and UK DPA compliance requirement.

**Content:**
- Last updated date
- What data we collect
- How we use it
- Who we share it with
- Data retention
- Your rights (access, erasure, portability)
- Cookie policy
- Contact: privacy@clendan.com

**Layout:**
- Clean prose, no marketing
- Table of contents sidebar
- IBM Plex Mono body text, generous line height

---

### 16. /terms

**Purpose:** Legal terms of service.

**Content:**
- Acceptance of terms
- Description of service
- User obligations
- Payment terms
- Intellectual property
- Limitation of liability
- Termination
- Governing law (England and Wales)
- Contact: legal@clendan.com

**Layout:** Same as privacy page.

---

### 17. /security-policy

**Purpose:** Responsible disclosure for security researchers.

**Content:**
- Scope: what systems are in scope
- How to report: security@clendan.com + PGP key if available
- Response SLA: acknowledge within 48 hours, update within 7 days
- What we ask of researchers
- What we commit to in return
- Out of scope: social engineering, DDoS, physical attacks

---

## ERROR + SYSTEM PAGES

---

### 18. /404 (Not Found)

**Content:**
- Large "404" in Syne bold, green
- "This page doesn't exist"
- "You might be looking for:" → links to Dashboard, Workers, Pricing, Docs
- "Back to home" button

---

### 19. /500 (Server Error)

**Content:**
- "Something went wrong on our end"
- "Our team has been notified automatically" (Sentry triggers)
- "Try again" button
- "If this keeps happening, contact support@clendan.com"
- Do not show raw error details

---

### 20. /maintenance

**Content:**
- Clendan logo
- "Clendan is under scheduled maintenance"
- Expected back online: [time]
- "Follow @clendan on X for updates"
- Estimated duration
- Static HTML only — no JS dependencies that might also be down

---

## GLOBAL RULES ACROSS ALL PAGES

### Layout
- Max content width: 1200px, centred
- Page padding: 32px desktop, 20px mobile
- All pages fully responsive: mobile / tablet / desktop

### Typography
- Headlines: Syne bold
- Body: IBM Plex Mono
- No system fonts except as fallback

### Colors
- Public pages: can use both dark (#0a0a0f bg) and light sections
- Dashboard: dark only
- Legal + error: dark only

### Performance
- Images: Next.js `<Image />` component only — no raw `<img>` tags
- Fonts: `next/font` — no external Google Fonts requests at runtime
- No unused CSS — Tailwind purge configured
- Core Web Vitals: LCP under 2.5s target

### SEO (marketing pages only)
- Every page has unique `<title>` and `<meta description>`
- Open Graph tags for social sharing
- Structured data (JSON-LD) on homepage and pricing page
- Sitemap.xml generated automatically via Next.js

### Accessibility
- All interactive elements keyboard navigable
- All images have alt text
- Color contrast meets WCAG AA minimum
- Focus states visible on all interactive elements

### Analytics
- PostHog loaded on all public and dashboard pages
- Key events to track:
  - `page_viewed` — every page
  - `cta_clicked` — every CTA button
  - `sign_up_started` — /sign-up page load
  - `onboarding_completed` — step 4 complete
  - `integration_connected` — first integration
  - `worker_deployed` — first worker
  - `first_execution` — first agent run
