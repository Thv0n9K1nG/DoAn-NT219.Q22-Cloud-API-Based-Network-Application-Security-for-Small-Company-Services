"""Stage 7 API skeleton for user profile operations."""

from fastapi import APIRouter

from app.models.schemas import ServiceInfo
from app.services.business_logic import service_summary


router = APIRouter()


@router.get("/users/metadata", response_model=ServiceInfo, tags=["users"])
async def users_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())

