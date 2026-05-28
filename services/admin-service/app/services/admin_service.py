"""Platform administration operations for tenants and operational counters."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment, Resource, Tenant, UserProfile
from app.models.schemas import TenantCreate
from shared.errors import APIError, ErrorCode


class AdminService:
    """Centralize platform-level DB changes behind platform_admin routes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tenants(self) -> list[Tenant]:
        result = await self.db.execute(select(Tenant).order_by(Tenant.name))
        return list(result.scalars().all())

    async def create_tenant(self, tenant_data: TenantCreate) -> Tenant:
        tenant = Tenant(id=uuid4(), name=tenant_data.name, status="active")
        self.db.add(tenant)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise APIError(409, ErrorCode.CONFLICT, "Tenant already exists") from exc
        await self.db.refresh(tenant)
        return tenant

    async def tenant_stats(self, tenant_id: UUID) -> dict[str, int]:
        tenant = await self.db.get(Tenant, tenant_id)
        if tenant is None:
            raise APIError(404, ErrorCode.NOT_FOUND, "Tenant not found")

        users = await self.db.scalar(select(func.count()).select_from(UserProfile).where(UserProfile.tenant_id == tenant_id))
        resources = await self.db.scalar(select(func.count()).select_from(Resource).where(Resource.tenant_id == tenant_id))
        payments = await self.db.scalar(select(func.count()).select_from(Payment).where(Payment.tenant_id == tenant_id))
        return {
            "users": int(users or 0),
            "resources": int(resources or 0),
            "payments": int(payments or 0),
        }

    async def rotate_tenant_key(self, tenant_id: UUID) -> str:
        tenant = await self.db.get(Tenant, tenant_id)
        if tenant is None:
            raise APIError(404, ErrorCode.NOT_FOUND, "Tenant not found")
        # Stage 8 records the operational intent; Vault key material handling stays behind the Vault client.
        return f"tenant-{tenant_id}"
