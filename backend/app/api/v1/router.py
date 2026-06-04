from fastapi import APIRouter
from app.api.v1 import dashboard, integrations, onboarding, plaid, tenants

v1_router = APIRouter()
v1_router.include_router(onboarding.router)
v1_router.include_router(tenants.router)
v1_router.include_router(integrations.router)
v1_router.include_router(plaid.router)
v1_router.include_router(dashboard.router)
