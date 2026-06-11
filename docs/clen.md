# Clen — Clendan's AI Assistant
# Build Phase A (Docs Assistant) after: website live, docs content written
# Build Phase B (Account Assistant) after: dashboard live, Invoice Processing Worker wired

---

## What Clen Is

Clen is Clendan's embedded AI assistant powered by Claude. It lives in two
places: the public marketing site (docs mode) and the authenticated dashboard
(account mode). In docs mode it answers questions about Clendan. In account
mode it knows the user's real data and can answer questions about their
specific account, guide them through tasks, and take actions with confirmation.

Clen is not a generic chatbot. It knows Clendan's full product, the user's
workers, their executions, their integrations, and their audit trail.
It speaks like a knowledgeable colleague, not a support ticket system.

---

## Two Phases

### Phase A — Docs Assistant (Marketing Site)
- Public, no auth required
- Available on all marketing pages and the docs page
- Knows everything in the Clendan docs
- Answers product, pricing, integration, and API questions
- Cannot access account data
- Build time: 1–2 days

### Phase B — Account Assistant (Dashboard)
- Authenticated users only
- Knows the user's real account data via live API calls
- Can answer questions, guide through tasks, and take actions
- Built on top of Phase A — same UI, extended capabilities
- Build time: 3–5 days after Phase A

---

## Personality and Tone

Clen speaks like a sharp, knowledgeable finance-tech colleague.

- Direct and precise — no filler, no "Great question!"
- Uses financial terminology correctly
- Confident about what it knows, honest about what it doesn't
- Does not over-explain unless asked
- Short answers for simple questions, detailed for complex ones
- Never says "I'm just an AI" — it's Clen, Clendan's assistant

Example responses:

User: "How do I set an approval threshold?"
Clen: "Go to Dashboard → Workers → Configure on the Invoice Processing Worker.
Set your auto-approve limit under Amount Thresholds. Anything below that
processes automatically. Above it routes to your approval queue."

User: "Why was the Acme invoice blocked?"
Clen: "The invoice from Acme Supplies (£6,200) was blocked because it exceeded
your block threshold of £5,000. It's sitting in your approval queue — want me
to pull up the full reasoning trace?"

---

## System Prompt (Phase A — Docs Mode)

```
You are Clen, the AI assistant for Clendan — an AI Financial Agent OS that
helps companies automate finance operations using autonomous AI workers.

You have full knowledge of:
- What Clendan is and how it works
- All 10 AI workers and what they do (Invoice Processing, AI Accountant,
  Reconciliation, Expense Control, Collections, Fraud Detection, Treasury,
  Revenue Recognition, Credit Underwriting, Compliance)
- The 5 standalone API tools (Invoice Parser, Receipt OCR, Document
  Reconciliation, Fraud Signal, Contract Extraction)
- All integrations (QuickBooks, Xero, Plaid, Stripe, GoCardless, TrueLayer,
  Codat, HubSpot, Gmail, Outlook, Google Drive)
- Pricing (Starter £299/mo, Growth £799/mo, Enterprise custom)
- The master-subagent architecture (Orchestrator routes to workers)
- Authentication (API keys, Bearer token)
- Policy engine (approval thresholds, supplier verification, currency rules)
- Audit trail (immutable, append-only, full reasoning traces)
- Webhooks and event types
- Multi-tenant organisation model and team roles

[FULL DOCS CONTENT INJECTED HERE AT BUILD TIME]

Personality:
- Direct and precise. No filler phrases.
- Use financial terminology correctly.
- Short answers for simple questions, detailed for complex ones.
- If you don't know something, say so — don't guess.
- Never say "I'm just an AI". You are Clen.
- If the user seems ready to sign up, mention they can start at
  app.clendan.com — but only once and only if relevant.

You do NOT have access to any user account data in this mode.
If asked about their specific account, workers, or executions,
tell them to log into their dashboard where you have full context.
```

---

## System Prompt (Phase B — Account Mode)

```
You are Clen, the AI assistant embedded in the Clendan dashboard.

[SAME BASE KNOWLEDGE AS PHASE A]

You also have access to this user's account data via tools.
Their organisation: {org_name}
Their active workers: {worker_list}
Their connected integrations: {integration_list}
Their plan: {plan_name}

You can:
1. Answer questions using their live account data by calling tools
2. Guide them through tasks step by step
3. Take actions on their behalf — but ALWAYS confirm before executing
   any action that modifies data (approvals, worker config, etc.)

Rules:
- Never take a modifying action without explicit user confirmation
- Always show what you're about to do before doing it
- If an action fails, explain what went wrong clearly
- Never expose raw API errors — translate to plain English
- If confidence in what the user wants is below 90%, ask to clarify
- Scope all data queries to their org — never reference other tenants

Available tools: [TOOL LIST INJECTED]
```

---

## UI Specification

### Marketing Site — Floating Chat Button

**Trigger:**
- Fixed position: bottom-right corner, 24px from edges
- Button: circle, 52px diameter, background `#00C853`, Clen icon (C mark)
- Hover: scale 1.05, subtle shadow
- Click: opens chat panel

**Chat Panel:**
- Slides up from bottom-right
- Width: 380px desktop, full-width mobile
- Height: 560px desktop, 70vh mobile
- Background: `#111118`
- Border: `1px solid #1a2a1a`
- Border radius: `8px` top corners only
- Drop shadow on left and top edges

**Header:**
- Clen logo mark + "Clen" in Syne bold
- Subtitle: "Clendan Assistant" in muted monospace
- Close button (X) top right
- Background: `#0a0a0f`, bottom border `1px solid #1a2a1a`

**Message Area:**
- Scrollable, padding `16px`
- User messages: right-aligned, background `#1a2a1a`, text `#e8f0e8`
- Clen messages: left-aligned, no background, text `#e8f0e8`
- Clen avatar: small green C mark before each response
- Timestamps: muted, `11px`, shown on hover
- Code blocks in responses: `#0a0a0f` background, monospace, green syntax

**Input Area:**
- Bottom of panel
- Text input: background `#0a0a0f`, border `1px solid #1a2a1a`
- Focus border: `1px solid #00C853`
- Send button: green arrow icon, disabled until text entered
- Enter to send, Shift+Enter for newline

**Welcome Message (shown on open):**
```
Hi, I'm Clen — Clendan's assistant.

Ask me anything about how Clendan works,
our API tools, integrations, or pricing.
```

**Suggested Prompts (shown before first message):**
- "How does invoice processing work?"
- "What integrations do you support?"
- "How much does Clendan cost?"
- "What's the Invoice Parser API?"

Clicking a prompt sends it immediately.

---

### Dashboard — Persistent Side Panel

**Trigger:**
- Button in top navbar: chat bubble icon + "Ask Clen"
- Background `#111118`, border `1px solid #1a2a1a`
- Click toggles panel open/closed

**Panel:**
- Slides in from right side of screen
- Width: 400px
- Full viewport height minus navbar
- Does NOT cover main content — main content area shrinks
- Persists across page navigation (conversation maintained in state)
- Background: `#0a0a0f`

**Header:**
- Same as marketing site but with additional context indicator:
  "Connected to your account" with green pulse dot

**Context Bar (below header):**
- Shows what Clen knows about the current page
- e.g. on `/dashboard/approvals`: "I can see your 3 pending approvals"
- e.g. on `/dashboard/workers`: "I can see your 2 active workers"
- Muted text, `11px`, IBM Plex Mono

**Action Confirmation UI:**
When Clen is about to take an action, it shows a confirmation card:

```
┌─────────────────────────────────────┐
│ ⚡ About to execute                  │
│                                     │
│ Approve invoice from Acme Supplies  │
│ Amount: £1,240                      │
│ Trace ID: trace-a1b2c3              │
│                                     │
│ [Confirm]          [Cancel]         │
└─────────────────────────────────────┘
```

Green Confirm button, ghost Cancel button.
Clen never executes without this confirmation being shown and clicked.

**Loading State:**
Three animated dots when Clen is thinking or calling a tool.
If calling a tool: shows which tool — "Checking your audit trail..."
"Looking at your workers..." "Fetching execution details..."

---

## Backend Architecture

### Frontend (Next.js)

```
frontend/
└── components/
    └── clen/
        ├── ClenButton.tsx          # Floating button (marketing site)
        ├── ClenPanel.tsx           # Main chat panel component
        ├── ClenMessage.tsx         # Individual message bubble
        ├── ClenInput.tsx           # Text input and send button
        ├── ClenSuggestions.tsx     # Suggested prompt buttons
        ├── ClenActionCard.tsx      # Action confirmation card
        ├── ClenContextBar.tsx      # Dashboard context indicator
        └── useClen.ts              # Hook managing chat state
```

**useClen.ts:**
```typescript
interface ClenMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  tool_calls?: ToolCall[]
  action_pending?: ActionConfirmation
}

interface ActionConfirmation {
  tool: string
  description: string
  params: Record<string, unknown>
  confirmed: boolean
}

export function useClen(mode: 'docs' | 'account') {
  const [messages, setMessages] = useState<ClenMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)

  async function sendMessage(content: string) { ... }
  async function confirmAction(messageId: string) { ... }
  async function cancelAction(messageId: string) { ... }
  function clearConversation() { ... }

  return { messages, isLoading, isOpen, setIsOpen, sendMessage,
           confirmAction, cancelAction, clearConversation }
}
```

### Backend (FastAPI)

```
backend/
└── app/
    └── clen/
        ├── router.py               # API routes for Clen
        ├── conversation.py         # Conversation management
        ├── context.py              # Build system prompt with user context
        ├── tools.py                # Tool definitions for account mode
        └── streaming.py            # SSE streaming response handler
```

**Routes:**

```
POST /v1/clen/chat           — send message, get response (streaming SSE)
POST /v1/clen/action/confirm — confirm a pending action
POST /v1/clen/action/cancel  — cancel a pending action
DELETE /v1/clen/conversation — clear conversation history
```

**Chat endpoint — streaming:**
```python
@router.post("/v1/clen/chat")
async def clen_chat(
    request: ClenChatRequest,
    current_user: CurrentUser = Depends(get_current_user_optional),
    response: Response = None
):
    """
    Stream Clen's response using Server-Sent Events.
    Mode determined by whether user is authenticated.
    Account mode tools only available when authenticated.
    """
    mode = "account" if current_user else "docs"
    system_prompt = await build_system_prompt(mode, current_user)

    # Stream Claude's response
    async def generate():
        async with anthropic_client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=request.messages,
            tools=get_tools(mode, current_user) if mode == "account" else []
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

            # Handle tool use
            final_message = await stream.get_final_message()
            for block in final_message.content:
                if block.type == "tool_use":
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': block.input})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## Tools Available in Account Mode

These are the same tools as the MCP but called server-side with the
user's credentials automatically scoped to their org.

```python
# backend/app/clen/tools.py

ACCOUNT_TOOLS = [
    {
        "name": "get_pending_approvals",
        "description": "Get all executions currently waiting for human approval in this account.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_execution_detail",
        "description": "Get full detail of a specific execution including reasoning trace and policy evaluation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trace_id": {"type": "string", "description": "The trace ID of the execution"}
            },
            "required": ["trace_id"]
        }
    },
    {
        "name": "get_audit_trail",
        "description": "Query the audit trail with optional filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "worker_type": {"type": "string"},
                "status": {"type": "string", "enum": ["auto", "approved", "rejected", "blocked"]},
                "from_date": {"type": "string"},
                "to_date": {"type": "string"},
                "limit": {"type": "integer", "default": 10}
            }
        }
    },
    {
        "name": "get_execution_stats",
        "description": "Get execution statistics for a time period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["1d", "7d", "30d", "90d"], "default": "7d"}
            }
        }
    },
    {
        "name": "list_workers",
        "description": "List all deployed workers and their current status.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_worker_status",
        "description": "Get detailed status and config of a specific worker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "worker_type": {"type": "string"}
            },
            "required": ["worker_type"]
        }
    },
    {
        "name": "list_integrations",
        "description": "List all integrations and their connection status.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_integration_status",
        "description": "Get detailed status of a specific integration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "integration_type": {"type": "string"}
            },
            "required": ["integration_type"]
        }
    },
    # ACTION TOOLS — require confirmation before execution
    {
        "name": "approve_execution",
        "description": "Approve a pending execution. ALWAYS show confirmation card before calling this.",
        "input_schema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string"},
                "note": {"type": "string"}
            },
            "required": ["approval_id"]
        }
    },
    {
        "name": "reject_execution",
        "description": "Reject a pending execution. ALWAYS show confirmation card before calling this. Reason is required.",
        "input_schema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string"},
                "reason": {"type": "string"}
            },
            "required": ["approval_id", "reason"]
        }
    },
    {
        "name": "pause_worker",
        "description": "Pause a running worker. ALWAYS show confirmation card before calling this.",
        "input_schema": {
            "type": "object",
            "properties": {
                "worker_type": {"type": "string"}
            },
            "required": ["worker_type"]
        }
    }
]
```

---

## Context Builder

```python
# backend/app/clen/context.py

async def build_system_prompt(mode: str, user: CurrentUser | None) -> str:
    base = load_docs_content()  # pre-loaded at startup from docs/ folder

    if mode == "docs":
        return DOCS_SYSTEM_PROMPT.format(docs=base)

    # Account mode — enrich with user's live context
    workers = await get_workers_summary(user.org_id)
    integrations = await get_integrations_summary(user.org_id)
    org = await get_org(user.org_id)
    stats = await get_execution_stats(user.org_id, period="7d")

    return ACCOUNT_SYSTEM_PROMPT.format(
        docs=base,
        org_name=org.name,
        plan=org.plan,
        worker_list=workers,
        integration_list=integrations,
        stats_summary=stats
    )

def load_docs_content() -> str:
    """
    Load and concatenate all MDX files from the docs/ folder.
    Strip MDX/JSX syntax, keep prose and structured content.
    Pre-load at app startup — not on every request.
    Cache result. Reload only on deployment.
    """
    ...
```

---

## Conversation History Management

Clendan stores conversation history in memory (React state) on the frontend.
It is not persisted to the database — conversations reset on page refresh.

**Why not persist:**
- Financial conversations contain sensitive data
- Users should not be surprised by old context affecting new answers
- Keeps the system simple for v1

**Message history sent on every request:**
```typescript
// Last 20 messages sent with every request
// Older messages dropped to manage context window
const recentMessages = messages.slice(-20)
```

**On dashboard navigation:**
- Conversation persists while the panel is open
- Conversation resets when the panel is closed and reopened
- This is intentional — fresh context per task

---

## Rate Limiting

Clen API calls are rate limited to prevent abuse:

| Plan | Messages per hour |
|---|---|
| Starter | 50 |
| Growth | 200 |
| Enterprise | Custom |
| Unauthenticated (docs mode) | 20 |

Rate limit headers returned on every response:
```
X-Clen-RateLimit-Limit: 200
X-Clen-RateLimit-Remaining: 187
X-Clen-RateLimit-Reset: 1716203600
```

When rate limited, Clen responds:
"You've reached your message limit for this hour. Upgrade to Growth for
200 messages per hour, or try again after [reset time]."

---

## Security Rules

- Clen backend route is protected — requires valid Clerk JWT in account mode
- All tool calls are scoped to the user's org_id from the JWT — never user-supplied
- Clen cannot access another tenant's data under any circumstance
- Action tools (approve, reject, pause) log the action to audit trail with actor: "clen/{user_id}"
- No financial data stored in conversation history on the server
- System prompt never returned to the client
- Tool results containing sensitive data (full credentials, raw tokens) are never passed to Claude

---

## Error Handling

**API errors from tools:**
```python
# Never pass raw errors to Claude
try:
    result = await call_tool(tool_name, tool_input)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 404:
        return {"error": "That resource was not found in your account."}
    elif e.response.status_code == 403:
        return {"error": "You don't have permission to access that."}
    else:
        return {"error": "Something went wrong fetching that data. Try again."}
```

**Connection errors:**
If the Clendan API is unreachable, Clen tells the user:
"I'm having trouble reaching your account data right now. I can still
answer questions about how Clendan works — try asking me that instead."

---

## Build Prompt for Claude Code

When ready to build, give Claude Code the following context:

```
Build Clen — Clendan's AI assistant — in two phases.

Phase A first (docs mode only):
1. Create the ClenButton, ClenPanel, ClenMessage, ClenInput, ClenSuggestions
   components in frontend/components/clen/
2. Create the useClen hook with message state management
3. Create the backend /v1/clen/chat endpoint with streaming SSE
4. Implement docs content loading from the docs/ folder into system prompt
5. Add the floating button to the marketing site layout
6. Style everything to Clendan brand — dark theme, #00C853 accents, IBM Plex Mono

Phase B after Phase A is working:
1. Extend the system prompt with user org context
2. Add all account mode tools to the backend
3. Implement the action confirmation card component
4. Add the dashboard panel with context bar
5. Add rate limiting per plan tier
6. Wire the panel toggle to the dashboard navbar
7. Add audit logging for all action tool calls

Read CLAUDE.md before starting. Keep all files under 500 lines.
Stream responses — never wait for the full response before rendering.
Never call the Anthropic API from the frontend — backend only.
```

---

## Phase Dependencies

**Phase A — Docs Assistant:**
- [ ] Website live at clendan.com
- [ ] Docs content written (at least introduction, quickstart, workers overview)
- [ ] Anthropic API key in backend env vars
- [ ] Marketing site deployed on Vercel

**Phase B — Account Assistant:**
- [ ] Dashboard live with real data
- [ ] Clerk auth working end to end
- [ ] Invoice Processing Worker wired
- [ ] At least one integration connected
- [ ] Phase A working and stable
