from fastapi import APIRouter
from app.api.v1 import dashboard, integrations, onboarding, plaid, tenants
from app.api.v1.transactions import router as transactions_router
from app.api.v1.events import router as events_router
from app.api.v1.parse.invoice import router as invoice_parse_router
from app.api.v1.parse.receipt import router as receipt_parse_router
from app.api.v1.agents.run import router as agents_router
from app.api.v1.approvals.respond import router as approvals_router
from app.api.v1.webhooks.plaid import router as plaid_webhook_router
from app.api.v1.webhooks.quickbooks import router as qb_webhook_router
from app.api.v1.webhooks.stripe import router as stripe_webhook_router
from app.api.v1.webhooks.xero import router as xero_webhook_router
from app.api.v1.dlq import router as dlq_router
from app.api.v1.tools import router as tools_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.reconcile import router as reconcile_router
from app.api.v1.fraud_score import router as fraud_score_router
from app.api.v1.parse_contract import router as parse_contract_router
from app.api.v1.organisations import router as organisations_router
from app.api.v1.xero import router as xero_router
from app.api.v1.freshbooks import router as freshbooks_router
from app.api.v1.stripe import router as stripe_routes_router
from app.api.v1.gocardless import router as gocardless_router
from app.api.v1.truelayer import router as truelayer_router
from app.api.v1.codat import router as codat_router
from app.api.v1.hubspot import router as hubspot_router
from app.api.v1.gmail import router as gmail_router
from app.api.v1.google_drive import router as google_drive_router
from app.api.v1.outlook import router as outlook_router
from app.api.v1.webhooks.gocardless import router as gocardless_webhook_router
from app.api.v1.webhooks.codat import router as codat_webhook_router
from app.api.v1.webhooks.gmail import router as gmail_webhook_router
from app.api.v1.webhooks.google_drive import router as google_drive_webhook_router
from app.api.v1.webhooks.outlook import router as outlook_webhook_router
from app.api.v1.execute import router as execute_router
from app.api.v1.execute_stats import router as execute_stats_router
from app.api.v1.square import router as square_router
from app.api.v1.paypal import router as paypal_router
from app.api.v1.webhooks.square import router as square_webhook_router
from app.api.v1.webhooks.paypal import router as paypal_webhook_router
from app.api.v1.generic import router as generic_router
from app.api.v1.sage import router as sage_router
from app.api.v1.adyen import router as adyen_router
from app.api.v1.wise import router as wise_router
from app.api.v1.mono import router as mono_router
from app.api.v1.webhooks.mono import router as mono_webhook_router
from app.api.v1.sap import router as sap_router
from app.api.v1.webhooks.sap import router as sap_webhook_router
from app.api.v1.salesforce import router as salesforce_router
from app.api.v1.webhooks.salesforce import router as salesforce_webhook_router
from app.api.v1.netsuite import router as netsuite_router
from app.api.v1.webhooks.netsuite import router as netsuite_webhook_router
from app.api.v1.dynamics import router as dynamics_router
from app.api.v1.webhooks.dynamics import router as dynamics_webhook_router
from app.api.v1.dropbox import router as dropbox_router
from app.api.v1.webhooks.dropbox import router as dropbox_webhook_router
from app.api.v1.onedrive import router as onedrive_router
from app.api.v1.webhooks.onedrive import router as onedrive_webhook_router
from app.api.v1.webhooks.freshbooks import router as freshbooks_webhook_router
from app.api.v1.webhooks.sage import router as sage_webhook_router
from app.api.v1.webhooks.hubspot import router as hubspot_webhook_router
from app.api.v1.webhooks.wise import router as wise_webhook_router
from app.api.v1.webhooks.truelayer import router as truelayer_webhook_router
from app.api.v1.webhooks.adyen import router as adyen_webhook_router
from app.clen.router import router as clen_router
from app.api.v1.budgets import router as budgets_router
from app.api.v1.currency import router as currency_router
from app.api.v1.document_intelligence_api import router as document_intelligence_router
from app.api.v1.document_actions import router as document_actions_router

v1_router = APIRouter()
v1_router.include_router(onboarding.router)
v1_router.include_router(organisations_router)
v1_router.include_router(tenants.router)
v1_router.include_router(integrations.router)
v1_router.include_router(plaid.router)
v1_router.include_router(xero_router)
v1_router.include_router(freshbooks_router)
v1_router.include_router(dashboard.router)
v1_router.include_router(events_router)
v1_router.include_router(invoice_parse_router)
v1_router.include_router(receipt_parse_router)
v1_router.include_router(agents_router)
v1_router.include_router(approvals_router)
v1_router.include_router(plaid_webhook_router)
v1_router.include_router(qb_webhook_router)
v1_router.include_router(stripe_webhook_router)
v1_router.include_router(xero_webhook_router)
v1_router.include_router(dlq_router)
v1_router.include_router(tools_router)
v1_router.include_router(decisions_router)
v1_router.include_router(api_keys_router)
v1_router.include_router(reconcile_router)
v1_router.include_router(fraud_score_router)
v1_router.include_router(parse_contract_router)
v1_router.include_router(stripe_routes_router)
v1_router.include_router(gocardless_router)
v1_router.include_router(truelayer_router)
v1_router.include_router(codat_router)
v1_router.include_router(hubspot_router)
v1_router.include_router(gmail_router)
v1_router.include_router(google_drive_router)
v1_router.include_router(outlook_router)
v1_router.include_router(gocardless_webhook_router)
v1_router.include_router(codat_webhook_router)
v1_router.include_router(gmail_webhook_router)
v1_router.include_router(google_drive_webhook_router)
v1_router.include_router(outlook_webhook_router)
v1_router.include_router(execute_router)
v1_router.include_router(execute_stats_router)
v1_router.include_router(square_router)
v1_router.include_router(paypal_router)
v1_router.include_router(square_webhook_router)
v1_router.include_router(paypal_webhook_router)
v1_router.include_router(clen_router)
v1_router.include_router(sage_router)
v1_router.include_router(adyen_router)
v1_router.include_router(wise_router)
v1_router.include_router(mono_router)
v1_router.include_router(mono_webhook_router)
v1_router.include_router(transactions_router)
v1_router.include_router(budgets_router)
v1_router.include_router(currency_router)
v1_router.include_router(sap_router)
v1_router.include_router(sap_webhook_router)
v1_router.include_router(salesforce_router)
v1_router.include_router(salesforce_webhook_router)
v1_router.include_router(netsuite_router)
v1_router.include_router(netsuite_webhook_router)
v1_router.include_router(dynamics_router)
v1_router.include_router(dynamics_webhook_router)
v1_router.include_router(dropbox_router)
v1_router.include_router(dropbox_webhook_router)
v1_router.include_router(onedrive_router)
v1_router.include_router(onedrive_webhook_router)
v1_router.include_router(freshbooks_webhook_router)
v1_router.include_router(sage_webhook_router)
v1_router.include_router(hubspot_webhook_router)
v1_router.include_router(wise_webhook_router)
v1_router.include_router(truelayer_webhook_router)
v1_router.include_router(adyen_webhook_router)
v1_router.include_router(document_intelligence_router)
v1_router.include_router(document_actions_router)
v1_router.include_router(generic_router)  # must be last — uses {slug} path params
