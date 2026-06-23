from datetime import datetime
from pydantic import BaseModel, EmailStr


class TenantResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    timezone: str = "UTC"


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    tenant_id: str


class OnboardingRequest(BaseModel):
    tenant_name: str


class OnboardingResponse(BaseModel):
    tenant: TenantResponse
    user: UserResponse
