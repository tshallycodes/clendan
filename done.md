# Done — Completed Tasks

## Document Intelligence — Full Redesign (2026-06-26)

Removed all invoice/contract/policy logic. Tool now has a clean two-path flow: receipt vs document.

### What changed
- **`backend/app/tools/document_intelligence.py`** — Full rewrite. Claude auto-classifies upload as `receipt` or `document`. Receipts extracted and auto-pushed to all configured accounting integrations (Xero, QuickBooks, FreshBooks). Documents get comprehensive AI analysis (summary, risks, loopholes, improvements). Word doc support via `python-docx`. `run_document_intelligence_job` no longer takes `document_type`. WORKER_VERSION=2.
- **`backend/app/api/v1/document_intelligence_api.py`** — Removed `document_type` query param; initial record uses `document_type="pending"`.
- **`backend/app/api/v1/document_actions.py`** — Removed `flag`, `push-integration`, `summarise` endpoints. Added `POST /{document_id}/ask` endpoint for follow-up Q&A via Claude.
- **`backend/app/tool.py`** — Removed `document_type` from two `enqueue_job` call sites.
- **`backend/pyproject.toml`** — Added `python-docx = "^1.1.0"`.
- **`frontend/components/dashboard/tools/ContractSummaryDrawer.tsx`** — Rewrote as `AskClenDrawer`: chat-style Q&A, message list, textarea with Enter-to-send.
- **`frontend/components/dashboard/tools/DocumentsTab.tsx`** — Full redesign: no type selector, multi-file upload, `ReceiptFields` (merchant/amount/date/category grid), `DocumentAnalysis` (summary + accordion for risks/loopholes/improvements), updated decision/label configs, upload accepts `.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp`.
- **`frontend/app/(dashboard)/tools/[slug]/GenericToolClient.tsx`** — Removed `connectedIntegrations` from `DocumentsTab`. Added `tool.howItWorks` override support with conditional subtitle.
- **`frontend/components/dashboard/tools/ToolAuditTab.tsx`** — Added `auto_pushed`, `analysed`, `push_failed`, `classification_failed` to `DocumentIntelligenceTrace`.
- **`frontend/app/(dashboard)/tools/tools-data.ts`** — Added `howItWorks?` to `ToolDef`. Updated document_intelligence entry with new `desc`, 8 capabilities, and custom 4-step howItWorks (Upload → Classify → Process → Audit).
- **`frontend/components/dashboard/tools/ToolConfigFields.tsx`** — Removed 14 stale invoice/policy/approval config fields. Kept only `accounting_integrations` multiselect with updated description.
- **`backend/app/clen/context.py`** — Updated Document Intelligence section to describe receipt/document split, auto-push, AI analysis, and the only config field.

### Decisions
- `accounting_integrations` is the ONLY config field — all other policy fields were obsolete.
- Classification uses first-page-only vision call (30s timeout), then a second full-document call for extraction/analysis.
- Word documents: lazy import of `python-docx` inside `_docx_to_text`.
- If no integrations configured and upload is a receipt → `push_failed` decision with clear error reason.
- `document_type` on DB record starts as `"pending"`, updated to `"receipt"` or `"document"` after processing.
- Decisions: `auto_pushed`, `push_failed`, `analysed`, `classification_failed`.
