from uuid import UUID, uuid4

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import set_tenant_context
from app.db.models import Payment
from app.models.schemas import PaymentCreate


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment_intent(self, data: PaymentCreate, tenant_id: str, user_id: str) -> Payment:
        if not settings.stripe_secret_key:
            raise RuntimeError("STRIPE_SECRET_KEY is not configured")

        tenant_uuid = UUID(tenant_id)
        await set_tenant_context(self.db, tenant_id)

        stripe.api_key = settings.stripe_secret_key
        intent = stripe.PaymentIntent.create(
            amount=data.amount,
            currency=data.currency.lower(),
            metadata={
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
            automatic_payment_methods={"enabled": True},
        )

        payment = Payment(
            id=uuid4(),
            tenant_id=tenant_uuid,
            user_id=user_id,
            stripe_payment_intent_id=intent["id"],
            amount=data.amount,
            currency=data.currency.lower(),
            status=intent["status"],
        )

        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def list_payments(self, tenant_id: str) -> list[Payment]:
        await set_tenant_context(self.db, tenant_id)
        result = await self.db.execute(
            select(Payment)
            .where(Payment.tenant_id == UUID(tenant_id))
            .order_by(Payment.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_payment(self, payment_id: UUID, tenant_id: str) -> Payment | None:
        await set_tenant_context(self.db, tenant_id)
        result = await self.db.execute(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.tenant_id == UUID(tenant_id),
            )
        )
        return result.scalar_one_or_none()

    async def update_status_by_intent_id(self, intent_id: str, status: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.stripe_payment_intent_id == intent_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            return None

        payment.status = status
        await self.db.commit()
        await self.db.refresh(payment)
        return payment