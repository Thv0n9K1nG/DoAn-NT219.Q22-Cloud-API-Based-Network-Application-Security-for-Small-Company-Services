"""Stage 7 API skeleton for platform administration."""

from fastapi import APIRouter

from app.models.schemas import ServiceInfo
from app.services.business_logic import service_summary


router = APIRouter()


@router.get("/admin/metadata", response_model=ServiceInfo, tags=["admin"])
async def admin_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())

