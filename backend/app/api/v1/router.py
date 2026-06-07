from fastapi import APIRouter
from app.api.v1 import dashboard, integrations, onboarding, plaid, tenants
from app.api.v1.events import router as events_router
from app.api.v1.parse.invoice import router as invoice_parse_router
from app.api.v1.parse.receipt import router as receipt_parse_router
from app.api.v1.agents.run import router as agents_router
from app.api.v1.approvals.respond import router as approvals_router
from app.api.v1.webhooks.plaid import router as plaid_webhook_router
from app.api.v1.webhooks.quickbooks import router as qb_webhook_router
from app.api.v1.webhooks.stripe import router as stripe_webhook_router
from app.api.v1.dlq import router as dlq_router
from app.api.v1.workers import router as workers_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.reconcile import router as reconcile_router
from app.api.v1.fraud_score import router as fraud_score_router
from app.api.v1.parse_contract import router as parse_contract_router
from app.api.v1.organisations import router as organisations_router

v1_router = APIRouter()
v1_router.include_router(onboarding.router)
v1_router.include_router(organisations_router)
v1_router.include_router(tenants.router)
v1_router.include_router(integrations.router)
v1_router.include_router(plaid.router)
v1_router.include_router(dashboard.router)
v1_router.include_router(events_router)
v1_router.include_router(invoice_parse_router)
v1_router.include_router(receipt_parse_router)
v1_router.include_router(agents_router)
v1_router.include_router(approvals_router)
v1_router.include_router(plaid_webhook_router)
v1_router.include_router(qb_webhook_router)
v1_router.include_router(stripe_webhook_router)
v1_router.include_router(dlq_router)
v1_router.include_router(workers_router)
v1_router.include_router(decisions_router)
v1_router.include_router(api_keys_router)
v1_router.include_router(reconcile_router)
v1_router.include_router(fraud_score_router)
v1_router.include_router(parse_contract_router)
