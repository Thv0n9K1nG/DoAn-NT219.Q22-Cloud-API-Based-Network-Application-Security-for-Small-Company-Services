"""DTOs for tenant-owned resource endpoints."""

from datetime import datetime
from ipaddress import ip_address
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


_BLOCKED_INTERNAL_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "vault",
    "opa",
    "postgres",
    "redis",
    "keycloak",
}


class ServiceInfo(BaseModel):
    service: str
    stage: str
    status: str


class ResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    data: dict = Field(default_factory=dict)
    url: HttpUrl | None = None

    @field_validator("url")
    @classmethod
    def validate_url_not_internal(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Reject internal targets before URL metadata can become a fetch primitive."""
        return _validate_public_http_url(value)


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    data: dict | None = None
    url: HttpUrl | None = None

    @field_validator("url")
    @classmethod
    def validate_url_not_internal(cls, value: HttpUrl | None) -> HttpUrl | None:
        """Reject internal targets before URL metadata can become a fetch primitive."""
        return _validate_public_http_url(value)


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    owner_user_id: str
    name: str
    data: dict
    url: str | None = None
    created_at: datetime


def _validate_public_http_url(value: HttpUrl | None) -> HttpUrl | None:
    if value is None:
        return value

    host = value.host
    if host is None or _is_internal_host(host):
        raise ValueError("URL must not target internal infrastructure")
    return value


def _is_internal_host(host: str) -> bool:
    normalized = host.rstrip(".").lower().strip("[]")
    if normalized in _BLOCKED_INTERNAL_HOSTS or normalized.endswith(".local"):
        return True

    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        return False

    return any(
        (
            parsed_ip.is_loopback,
            parsed_ip.is_link_local,
            parsed_ip.is_private,
            parsed_ip.is_reserved,
            parsed_ip.is_unspecified,
        )
    )
