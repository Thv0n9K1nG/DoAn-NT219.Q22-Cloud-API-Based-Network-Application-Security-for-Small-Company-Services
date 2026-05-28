"""DTOs for user profile endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class ServiceInfo(BaseModel):
    service: str
    stage: str
    status: str


class UserCreate(BaseModel):
    tenant_id: UUID | None = None
    keycloak_user_id: str
    email: EmailStr
    role: Literal["tenant_admin", "tenant_user", "platform_admin"]


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: Literal["tenant_admin", "tenant_user", "platform_admin"] | None = None
    status: Literal["active", "disabled", "deleted"] | None = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    keycloak_user_id: str
    tenant_id: UUID
    email: EmailStr
    role: str
    status: str
    created_at: datetime
