"""Persistence operations for tenant-owned resources."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import set_tenant_context
from app.db.models import Resource
from app.models.schemas import ResourceCreate, ResourceUpdate
from shared.errors import APIError, ErrorCode


class ResourceService:
    """Encapsulate SQLAlchemy operations while routes enforce ownership policy."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_resources(self, *, tenant_id: UUID | None, include_all: bool = False) -> list[Resource]:
        if tenant_id is not None:
            await set_tenant_context(self.db, str(tenant_id))

        query = select(Resource).order_by(Resource.created_at.desc())
        if tenant_id is not None and not include_all:
            query = query.where(Resource.tenant_id == tenant_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_resource(self, resource_id: UUID) -> Resource | None:
        result = await self.db.execute(select(Resource).where(Resource.id == resource_id))
        return result.scalar_one_or_none()

    async def create_resource(
        self,
        *,
        resource_data: ResourceCreate,
        tenant_id: UUID,
        owner_user_id: str,
    ) -> Resource:
        await set_tenant_context(self.db, str(tenant_id))
        resource = Resource(
            id=uuid4(),
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            name=resource_data.name,
            data=resource_data.data,
            url=str(resource_data.url) if resource_data.url is not None else None,
        )
        self.db.add(resource)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise APIError(409, ErrorCode.CONFLICT, "Resource already exists in this tenant") from exc
        await self.db.refresh(resource)
        return resource

    async def update_resource(self, *, resource: Resource, resource_data: ResourceUpdate) -> Resource:
        updates = resource_data.model_dump(exclude_unset=True)
        if "url" in updates and updates["url"] is not None:
            updates["url"] = str(updates["url"])
        for field, value in updates.items():
            setattr(resource, field, value)

        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise APIError(409, ErrorCode.CONFLICT, "Resource update conflicts with existing data") from exc
        await self.db.refresh(resource)
        return resource

    async def delete_resource(self, *, resource: Resource) -> None:
        await self.db.delete(resource)
        await self.db.commit()
