"""Unauthenticated Stripe webhook endpoint with HMAC verification."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.v1.dependencies import get_payment_service
from app.models.schemas import WebhookAck
from app.services.payment_service import PaymentService
from shared.errors import APIError, ErrorCode


router = APIRouter(tags=["webhooks"])
logger = logging.getLogger("payment-service")


@router.post("/webhooks/stripe", response_model=WebhookAck, status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    payment_service: PaymentService = Depends(get_payment_service),
) -> WebhookAck:
    if not stripe_signature:
        logger.warning(
            "security.invalid_webhook_signature",
            extra={"event": "security.invalid_webhook_signature", "webhook_provider": "stripe", "reason": "missing_signature"},
        )
        raise APIError(400, ErrorCode.BAD_REQUEST, "Missing Stripe signature")

    payload = await request.body()
    try:
        event = payment_service.verify_stripe_event(payload, stripe_signature)
    except APIError:
        logger.warning(
            "security.invalid_webhook_signature",
            extra={"event": "security.invalid_webhook_signature", "webhook_provider": "stripe", "reason": "verification_failed"},
        )
        raise
    except Exception as exc:
        logger.warning(
            "security.invalid_webhook_signature",
            extra={"event": "security.invalid_webhook_signature", "webhook_provider": "stripe", "reason": "unexpected_error"},
        )
        raise APIError(400, ErrorCode.BAD_REQUEST, "Invalid Stripe webhook signature") from exc

    result = await payment_service.process_stripe_event(event)
    return WebhookAck(
        received=True,
        event_type=result.event_type,
        payment_intent_id=result.payment_intent_id,
        duplicate=result.duplicate,
        status=result.status,
    )
