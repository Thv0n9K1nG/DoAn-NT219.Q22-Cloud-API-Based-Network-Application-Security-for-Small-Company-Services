"""DTOs for tenant-owned resource endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ServiceInfo(BaseModel):
    service: str
    stage: str
    status: str


class ResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    data: dict = Field(default_factory=dict)
    url: HttpUrl | None = None


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    data: dict | None = None
    url: HttpUrl | None = None


class ResourceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    owner_user_id: str
    name: str
    data: dict
    url: str | None = None
    created_at: datetime

