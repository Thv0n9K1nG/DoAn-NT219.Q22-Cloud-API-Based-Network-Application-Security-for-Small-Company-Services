from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user, require_roles
from app.db.database import get_db
from app.models.schemas import PaymentCreate, PaymentResponse, ServiceInfo
from app.services.business_logic import service_summary
from app.services.payment_service import PaymentService
from shared.errors import APIError, ErrorCode


router = APIRouter()


@router.get("/payments/metadata", response_model=ServiceInfo, tags=["payments"])
async def payments_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())


@router.post("/payments/intent", response_model=PaymentResponse, tags=["payments"])
async def create_payment_intent(
    payload: PaymentCreate,
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin", "platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    if current_user.tenant_id is None:
        raise APIError(400, ErrorCode.BAD_REQUEST, "tenant_id claim is required")

    service = PaymentService(db)
    payment = await service.create_payment_intent(
        data=payload,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
    )
    return PaymentResponse.model_validate(payment, from_attributes=True)


@router.get("/payments", response_model=list[PaymentResponse], tags=["payments"])
async def list_payments(
    current_user: CurrentUser = Depends(require_roles("tenant_admin", "platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentResponse]:
    if current_user.tenant_id is None:
        raise APIError(400, ErrorCode.BAD_REQUEST, "tenant_id claim is required")

    service = PaymentService(db)
    payments = await service.list_payments(current_user.tenant_id)
    return [PaymentResponse.model_validate(payment, from_attributes=True) for payment in payments]


@router.get("/payments/{payment_id}", response_model=PaymentResponse, tags=["payments"])
async def get_payment(
    payment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    if current_user.tenant_id is None:
        raise APIError(400, ErrorCode.BAD_REQUEST, "tenant_id claim is required")

    service = PaymentService(db)
    payment = await service.get_payment(payment_id, current_user.tenant_id)
    if payment is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "Payment not found")

    return PaymentResponse.model_validate(payment, from_attributes=True)