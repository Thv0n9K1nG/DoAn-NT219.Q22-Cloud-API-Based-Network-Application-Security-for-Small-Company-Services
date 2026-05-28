"""Tenant-owned resource API with service-level BOLA protection."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Resource
from app.models.schemas import ResourceCreate, ResourceResponse, ResourceUpdate, ServiceInfo
from app.services.business_logic import service_summary
from app.services.resource_service import ResourceService
from shared.errors import APIError, ErrorCode
from shared.security_middleware import CurrentUser, require_roles


router = APIRouter()
logger = logging.getLogger("resource-service")


@router.get("/resources/metadata", response_model=ServiceInfo, tags=["resources"])
async def resources_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())


@router.get(
    "/resources",
    response_model=list[ResourceResponse],
    tags=["resources"],
)
async def list_resources(
    tenant_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin", "platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> list[Resource]:
    service = ResourceService(db)
    scope_tenant_id = tenant_id if "platform_admin" in current_user.roles else _required_tenant_id(current_user)
    resources = await service.list_resources(
        tenant_id=scope_tenant_id,
        include_all="platform_admin" in current_user.roles and tenant_id is None,
    )
    logger.info("resource.list", extra={"event": "resource.list", "target_tenant_id": str(scope_tenant_id) if scope_tenant_id else None})
    return resources


@router.get(
    "/resources/{resource_id}",
    response_model=ResourceResponse,
    tags=["resources"],
)
async def get_resource(
    resource_id: UUID,
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin", "platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> Resource:
    service = ResourceService(db)
    resource = await service.get_resource(resource_id)
    if resource is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "Resource not found")
    _authorize_resource_access(current_user, resource)
    logger.info("resource.read", extra={"event": "resource.read", "resource_id": str(resource.id)})
    return resource


@router.post(
    "/resources",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["resources"],
)
async def create_resource(
    resource_data: ResourceCreate,
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> Resource:
    service = ResourceService(db)
    tenant_id = _required_tenant_id(current_user)
    resource = await service.create_resource(
        resource_data=resource_data,
        tenant_id=tenant_id,
        owner_user_id=current_user.user_id,
    )
    logger.info("resource.create", extra={"event": "resource.create", "resource_id": str(resource.id)})
    return resource


@router.put(
    "/resources/{resource_id}",
    response_model=ResourceResponse,
    tags=["resources"],
)
async def update_resource(
    resource_id: UUID,
    resource_data: ResourceUpdate,
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> Resource:
    service = ResourceService(db)
    resource = await service.get_resource(resource_id)
    if resource is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "Resource not found")
    _authorize_resource_access(current_user, resource)
    updated = await service.update_resource(resource=resource, resource_data=resource_data)
    logger.info("resource.update", extra={"event": "resource.update", "resource_id": str(updated.id)})
    return updated


@router.delete(
    "/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["resources"],
)
async def delete_resource(
    resource_id: UUID,
    current_user: CurrentUser = Depends(require_roles("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    service = ResourceService(db)
    resource = await service.get_resource(resource_id)
    if resource is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "Resource not found")
    _authorize_resource_access(current_user, resource)
    await service.delete_resource(resource=resource)
    logger.info("resource.delete", extra={"event": "resource.delete", "resource_id": str(resource.id)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _required_tenant_id(user: CurrentUser) -> UUID:
    if user.tenant_id is None:
        raise APIError(403, ErrorCode.ACCESS_DENIED, "Tenant context is required")
    return UUID(user.tenant_id)


def _authorize_resource_access(user: CurrentUser, resource: Resource) -> None:
    if "platform_admin" in user.roles:
        return
    user_tenant_id = _required_tenant_id(user)
    if resource.tenant_id == user_tenant_id:
        return

    logger.warning(
        "security.bola_attempt",
        extra={
            "event": "security.bola_attempt",
            "user_id": user.user_id,
            "attacker_tenant_id": str(user_tenant_id),
            "resource_id": str(resource.id),
            "resource_tenant_id": str(resource.tenant_id),
        },
    )
    raise APIError(403, ErrorCode.ACCESS_DENIED, "Access denied")
