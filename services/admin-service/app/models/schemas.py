"""DTOs for platform administration endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    service: str
    stage: str
    status: str


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantResponse(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime


class TenantStatsResponse(BaseModel):
    tenant_id: UUID
    users: int
    resources: int
    payments: int


class KeyRotationResponse(BaseModel):
    tenant_id: UUID
    status: str
    new_key_name: str

