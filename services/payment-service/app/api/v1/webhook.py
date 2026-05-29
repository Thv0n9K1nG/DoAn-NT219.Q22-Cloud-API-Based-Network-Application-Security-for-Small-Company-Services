import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models.schemas import WebhookAck
from app.services.payment_service import PaymentService


router = APIRouter()


@router.post("/webhooks/stripe", response_model=WebhookAck, tags=["webhooks"])
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> WebhookAck:
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook payload") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") from exc

    event_type = event["type"]
    payment_service = PaymentService(db)

    if event_type in {"payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.canceled"}:
        intent = event["data"]["object"]
        await payment_service.update_status_by_intent_id(
            intent_id=intent["id"],
            status=intent["status"],
        )

    return WebhookAck(received=True, event_type=event_type)