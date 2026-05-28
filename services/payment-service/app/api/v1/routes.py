"""Stage 7 API skeleton for payments and webhooks."""

from fastapi import APIRouter

from app.models.schemas import ServiceInfo
from app.services.business_logic import service_summary


router = APIRouter()


@router.get("/payments/metadata", response_model=ServiceInfo, tags=["payments"])
async def payments_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())


@router.get("/webhooks/metadata", response_model=ServiceInfo, tags=["webhooks"])
async def webhooks_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())

