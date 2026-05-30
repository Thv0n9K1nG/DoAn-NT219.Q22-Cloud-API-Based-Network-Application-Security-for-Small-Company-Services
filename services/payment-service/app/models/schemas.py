"""DTOs for payment and webhook endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceInfo(BaseModel):
    service: str
    stage: str
    status: str


class PaymentCreate(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(default="usd", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"usd", "vnd"}:
            raise ValueError("currency must be one of: usd, vnd")
        return normalized


class PaymentIntentResponse(BaseModel):
    payment_id: UUID
    payment_intent_id: str
    client_secret: str
    status: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: str
    stripe_payment_intent_id: str
    amount: int
    currency: str
    status: str
    created_at: datetime


class WebhookAck(BaseModel):
    received: bool
    event_type: str | None = None
    payment_intent_id: str | None = None
    duplicate: bool = False
    status: str | None = None
