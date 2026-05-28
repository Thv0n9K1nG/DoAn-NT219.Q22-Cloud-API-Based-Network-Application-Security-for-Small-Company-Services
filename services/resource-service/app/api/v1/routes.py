"""Stage 7 API skeleton for tenant-owned resources."""

from fastapi import APIRouter

from app.models.schemas import ServiceInfo
from app.services.business_logic import service_summary


router = APIRouter()


@router.get("/resources/metadata", response_model=ServiceInfo, tags=["resources"])
async def resources_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())

