"""Platform administration API guarded by platform_admin role checks."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Tenant
from app.models.schemas import KeyRotationResponse, ServiceInfo, TenantCreate, TenantResponse, TenantStatsResponse
from app.services.business_logic import service_summary
from app.services.admin_service import AdminService
from shared.security_middleware import CurrentUser, require_roles


router = APIRouter()
logger = logging.getLogger("admin-service")


@router.get("/admin/metadata", response_model=ServiceInfo, tags=["admin"])
async def admin_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())


@router.get(
    "/admin/tenants",
    response_model=list[TenantResponse],
    tags=["admin"],
)
async def list_tenants(
    _: CurrentUser = Depends(require_roles("platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> list[Tenant]:
    service = AdminService(db)
    return await service.list_tenants()


@router.post(
    "/admin/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def create_tenant(
    tenant_data: TenantCreate,
    _: CurrentUser = Depends(require_roles("platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    service = AdminService(db)
    tenant = await service.create_tenant(tenant_data)
    logger.info("admin.tenant_onboard", extra={"event": "admin.tenant_onboard", "target_tenant_id": str(tenant.id)})
    return tenant


@router.get(
    "/admin/tenants/{tenant_id}/stats",
    response_model=TenantStatsResponse,
    tags=["admin"],
)
async def tenant_stats(
    tenant_id: UUID,
    _: CurrentUser = Depends(require_roles("platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> TenantStatsResponse:
    service = AdminService(db)
    stats = await service.tenant_stats(tenant_id)
    return TenantStatsResponse(tenant_id=tenant_id, **stats)


@router.post(
    "/admin/tenants/{tenant_id}/keys",
    response_model=KeyRotationResponse,
    tags=["admin"],
)
async def rotate_tenant_key(
    tenant_id: UUID,
    _: CurrentUser = Depends(require_roles("platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> KeyRotationResponse:
    service = AdminService(db)
    key_name = await service.rotate_tenant_key(tenant_id)
    logger.info("admin.tenant_key_rotate", extra={"event": "admin.tenant_key_rotate", "target_tenant_id": str(tenant_id)})
    return KeyRotationResponse(tenant_id=tenant_id, status="rotation-recorded", new_key_name=key_name)
