"""Tenant-scoped payment API backed by Stripe Payment Intents."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.dependencies import get_payment_service
from app.db.models import Payment
from app.models.schemas import PaymentCreate, PaymentIntentResponse, PaymentResponse, ServiceInfo
from app.services.business_logic import service_summary
from app.services.payment_service import PaymentService
from shared.errors import APIError, ErrorCode
from shared.security_middleware import CurrentUser, require_roles


router = APIRouter()
logger = logging.getLogger("payment-service")


@router.get("/payments/metadata", response_model=ServiceInfo, tags=["payments"])
async def payments_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())


@router.get("/webhooks/metadata", response_model=ServiceInfo, tags=["webhooks"])
async def webhooks_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())


@router.post(
    "/payments/intent",
    response_model=PaymentIntentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["payments"],
)
async def create_payment_intent(
    payment_data: PaymentCreate,
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin")),
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentIntentResponse:
    tenant_id = _required_tenant_id(current_user)
    result = await payment_service.create_payment_intent(
        payment_data=payment_data,
        tenant_id=tenant_id,
        user_id=current_user.user_id,
    )
    logger.info(
        "payment.intent_created",
        extra={"event": "payment.intent_created", "payment_intent_id": result.payment.stripe_payment_intent_id},
    )
    return PaymentIntentResponse(
        payment_id=result.payment.id,
        payment_intent_id=result.payment.stripe_payment_intent_id,
        client_secret=result.client_secret,
        status=result.payment.status,
    )


@router.get("/payments", response_model=list[PaymentResponse], tags=["payments"])
async def list_payments(
    tenant_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(require_roles("tenant_admin", "platform_admin")),
    payment_service: PaymentService = Depends(get_payment_service),
) -> list[Payment]:
    if "platform_admin" in current_user.roles:
        return await payment_service.list_payments(
            tenant_id=tenant_id,
            include_all=tenant_id is None,
        )

    return await payment_service.list_payments(tenant_id=_required_tenant_id(current_user))


@router.get("/payments/{payment_id}", response_model=PaymentResponse, tags=["payments"])
async def get_payment(
    payment_id: UUID,
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin", "platform_admin")),
    payment_service: PaymentService = Depends(get_payment_service),
) -> Payment:
    payment = await payment_service.get_payment(payment_id)
    if payment is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "Payment not found")
    if "platform_admin" not in current_user.roles and payment.tenant_id != _required_tenant_id(current_user):
        logger.warning(
            "security.payment_bola_attempt",
            extra={
                "event": "security.payment_bola_attempt",
                "user_id": current_user.user_id,
                "attacker_tenant_id": current_user.tenant_id,
                "payment_id": str(payment.id),
                "payment_tenant_id": str(payment.tenant_id),
            },
        )
        raise APIError(403, ErrorCode.ACCESS_DENIED, "Access denied")
    return payment


def _required_tenant_id(user: CurrentUser) -> UUID:
    if user.tenant_id is None:
        raise APIError(403, ErrorCode.ACCESS_DENIED, "Tenant context is required")
    return UUID(user.tenant_id)
