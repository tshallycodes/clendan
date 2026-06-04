from fastapi import APIRouter
from app.api.v1 import dashboard, integrations, onboarding, plaid, tenants
from app.api.v1.parse.invoice import router as parse_router
from app.api.v1.agents.run import router as agents_router
from app.api.v1.approvals.respond import router as approvals_router

v1_router = APIRouter()
v1_router.include_router(onboarding.router)
v1_router.include_router(tenants.router)
v1_router.include_router(integrations.router)
v1_router.include_router(plaid.router)
v1_router.include_router(dashboard.router)
v1_router.include_router(parse_router)
v1_router.include_router(agents_router)
v1_router.include_router(approvals_router)
