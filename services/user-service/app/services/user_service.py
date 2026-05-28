"""Database-backed user profile operations with tenant-scoped access helpers."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserProfile
from app.models.schemas import UserCreate, UserUpdate
from shared.errors import APIError, ErrorCode
from shared.security_middleware import CurrentUser


class UserService:
    """Keep persistence separate from route-level authorization decisions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self, *, current_user: CurrentUser, tenant_id: UUID | None = None) -> list[UserProfile]:
        query = select(UserProfile).order_by(UserProfile.email)
        if "platform_admin" in current_user.roles:
            if tenant_id is not None:
                query = query.where(UserProfile.tenant_id == tenant_id)
        else:
            query = query.where(UserProfile.tenant_id == UUID(str(current_user.tenant_id)))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_user(self, user_id: str) -> UserProfile | None:
        query = select(UserProfile)
        try:
            query = query.where(UserProfile.id == UUID(user_id))
        except ValueError:
            query = query.where(UserProfile.keycloak_user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, *, email: str, tenant_id: UUID) -> UserProfile | None:
        result = await self.db.execute(
            select(UserProfile).where(
                UserProfile.email == email,
                UserProfile.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_user(self, *, user_data: UserCreate, tenant_id: UUID) -> UserProfile:
        profile = UserProfile(
            id=uuid4(),
            keycloak_user_id=user_data.keycloak_user_id,
            tenant_id=tenant_id,
            email=str(user_data.email),
            role=user_data.role,
            status="active",
        )
        self.db.add(profile)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise APIError(409, ErrorCode.CONFLICT, "User profile already exists") from exc
        await self.db.refresh(profile)
        return profile

    async def update_user(self, *, profile: UserProfile, user_data: UserUpdate) -> UserProfile:
        updates = user_data.model_dump(exclude_unset=True)
        if "email" in updates and updates["email"] is not None:
            updates["email"] = str(updates["email"])
        for field, value in updates.items():
            setattr(profile, field, value)

        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise APIError(409, ErrorCode.CONFLICT, "User profile update conflicts with existing data") from exc
        await self.db.refresh(profile)
        return profile

    async def deactivate_user(self, *, profile: UserProfile) -> None:
        # The Stage 3 schema models soft-delete as "disabled"; hard deletes remain avoided.
        profile.status = "disabled"
        await self.db.commit()
