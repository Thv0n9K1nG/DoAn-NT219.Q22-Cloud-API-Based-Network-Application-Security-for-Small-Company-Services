"""User profile API with tenant-aware authorization rules."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import UserProfile
from app.models.schemas import ServiceInfo, UserCreate, UserProfileResponse, UserUpdate
from app.services.business_logic import service_summary
from app.services.user_service import UserService
from shared.errors import APIError, ErrorCode
from shared.security_middleware import CurrentUser, require_roles


router = APIRouter()
logger = logging.getLogger("user-service")


@router.get("/users/metadata", response_model=ServiceInfo, tags=["users"])
async def users_metadata() -> ServiceInfo:
    return ServiceInfo(**service_summary())


@router.get(
    "/users",
    response_model=list[UserProfileResponse],
    tags=["users"],
)
async def list_users(
    tenant_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(require_roles("tenant_admin", "platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> list[UserProfile]:
    service = UserService(db)
    users = await service.list_users(current_user=current_user, tenant_id=tenant_id)
    if "platform_admin" in current_user.roles and tenant_id is not None:
        logger.info(
            "user.list.cross_tenant",
            extra={"event": "user.list", "target_tenant_id": str(tenant_id)},
        )
    else:
        logger.info("user.list", extra={"event": "user.list"})
    return users


@router.get(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    tags=["users"],
)
async def get_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_roles("tenant_user", "tenant_admin", "platform_admin")),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    service = UserService(db)
    profile = await service.get_user(user_id)
    if profile is None and _is_self_lookup(user_id, current_user):
        profile = await service.get_user_by_email(
            email=current_user.email or "",
            tenant_id=_required_tenant_id(current_user),
        )
    if profile is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "User profile not found")
    _authorize_user_read(current_user, profile)
    return profile


@router.post(
    "/users",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["users"],
)
async def create_user(
    user_data: UserCreate,
    current_user: CurrentUser = Depends(require_roles("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    tenant_id = _required_tenant_id(current_user)
    if user_data.tenant_id is not None and user_data.tenant_id != tenant_id:
        raise APIError(403, ErrorCode.ACCESS_DENIED, "Cannot create users outside your tenant")

    service = UserService(db)
    profile = await service.create_user(user_data=user_data, tenant_id=tenant_id)
    logger.info("user.create", extra={"event": "user.create", "target_user_id": str(profile.id)})
    return profile


@router.put(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    tags=["users"],
)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: CurrentUser = Depends(require_roles("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    service = UserService(db)
    profile = await service.get_user(user_id)
    if profile is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "User profile not found")
    _authorize_same_tenant_admin(current_user, profile)
    updated = await service.update_user(profile=profile, user_data=user_data)
    logger.info("user.update", extra={"event": "user.update", "target_user_id": str(updated.id)})
    return updated


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users"],
)
async def deactivate_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_roles("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    service = UserService(db)
    profile = await service.get_user(user_id)
    if profile is None:
        raise APIError(404, ErrorCode.NOT_FOUND, "User profile not found")
    _authorize_same_tenant_admin(current_user, profile)
    await service.deactivate_user(profile=profile)
    logger.info("user.deactivate", extra={"event": "user.deactivate", "target_user_id": str(profile.id)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _required_tenant_id(user: CurrentUser) -> UUID:
    if user.tenant_id is None:
        raise APIError(403, ErrorCode.ACCESS_DENIED, "Tenant context is required")
    return UUID(user.tenant_id)


def _authorize_user_read(user: CurrentUser, profile: UserProfile) -> None:
    if "platform_admin" in user.roles:
        return
    if profile.keycloak_user_id == user.user_id and str(profile.tenant_id) == user.tenant_id:
        return
    if user.email and profile.email == user.email and str(profile.tenant_id) == user.tenant_id:
        return
    if "tenant_admin" in user.roles and str(profile.tenant_id) == user.tenant_id:
        return
    raise APIError(403, ErrorCode.ACCESS_DENIED, "Cannot access user outside your tenant")


def _authorize_same_tenant_admin(user: CurrentUser, profile: UserProfile) -> None:
    tenant_id = _required_tenant_id(user)
    if profile.tenant_id != tenant_id:
        raise APIError(403, ErrorCode.ACCESS_DENIED, "Cannot manage users outside your tenant")


def _is_self_lookup(user_id: str, user: CurrentUser) -> bool:
    return user_id in {user.user_id, "me"} and user.email is not None
