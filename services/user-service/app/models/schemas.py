"""DTOs for user profile endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class ServiceInfo(BaseModel):
    service: str
    stage: str
    status: str


class UserCreate(BaseModel):
    keycloak_user_id: str
    email: EmailStr
    role: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: str | None = None
    status: str | None = None


class UserProfileResponse(BaseModel):
    id: UUID
    keycloak_user_id: str
    tenant_id: UUID
    email: EmailStr
    role: str
    status: str
    created_at: datetime

