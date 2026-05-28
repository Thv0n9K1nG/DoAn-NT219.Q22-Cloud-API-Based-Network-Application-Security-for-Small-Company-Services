"""DTOs for payment and webhook endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    service: str
    stage: str
    status: str


class PaymentCreate(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(default="usd", min_length=3, max_length=3)


class PaymentResponse(BaseModel):
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

