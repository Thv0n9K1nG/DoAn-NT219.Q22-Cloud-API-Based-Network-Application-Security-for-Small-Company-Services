"""Stripe payment orchestration and webhook processing."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import anyio
import stripe
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import set_tenant_context
from app.db.models import Payment, StripeWebhookEvent
from app.models.schemas import PaymentCreate
from shared.errors import APIError, ErrorCode
from shared.pqc_signing import MLDSASigner, WEBHOOK_SIGNING_KEY_PATH
from shared.vault_client import VaultClient
from shared.webhook_signer import create_webhook_signature_headers


ALLOWED_CURRENCIES = {"usd", "vnd"}
# Vault KV paths and lab sentinels are identifiers, not secret material.
STRIPE_SECRET_KEY_PATH = "stripe/secret_key"  # nosec B105
STRIPE_WEBHOOK_SECRET_PATH = "stripe/webhook_secret"  # nosec B105
LAB_STRIPE_SECRET_PLACEHOLDER = "sk_test_lab_placeholder"  # nosec B105
LAB_STRIPE_WEBHOOK_PLACEHOLDER = "whsec_lab_placeholder"

logger = logging.getLogger("payment-service")


@dataclass(frozen=True)
class PaymentIntentResult:
    payment: Payment
    client_secret: str


@dataclass(frozen=True)
class StripeEventResult:
    event_id: str
    event_type: str
    payment_intent_id: str | None
    duplicate: bool = False
    status: str | None = None


class PaymentService:
    """Coordinate tenant-scoped payment records with Stripe sandbox APIs."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        stripe_secret_key: str | None = None,
        stripe_webhook_secret: str | None = None,
        vault_client: VaultClient | None = None,
        webhook_signer: MLDSASigner | None = None,
    ):
        self.db = db
        self._stripe_secret_key = stripe_secret_key
        self._stripe_webhook_secret = stripe_webhook_secret
        self._vault_client = vault_client
        self._webhook_signer = webhook_signer

    async def create_payment_intent(
        self,
        *,
        payment_data: PaymentCreate,
        tenant_id: UUID,
        user_id: str,
    ) -> PaymentIntentResult:
        await set_tenant_context(self.db, str(tenant_id))
        currency = payment_data.currency.lower()
        if currency not in ALLOWED_CURRENCIES:
            raise APIError(422, ErrorCode.BAD_REQUEST, f"Unsupported currency: {currency}")

        metadata = {"tenant_id": str(tenant_id), "user_id": user_id}
        stripe_intent = await self._create_stripe_payment_intent(
            amount=payment_data.amount,
            currency=currency,
            metadata=metadata,
        )
        payment = Payment(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            stripe_payment_intent_id=_stripe_value(stripe_intent, "id"),
            amount=payment_data.amount,
            currency=currency,
            status=_stripe_value(stripe_intent, "status", default="requires_payment_method"),
        )
        self.db.add(payment)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise APIError(409, ErrorCode.CONFLICT, "Payment intent already exists") from exc

        await self.db.refresh(payment)
        return PaymentIntentResult(payment=payment, client_secret=_stripe_value(stripe_intent, "client_secret"))

    async def list_payments(self, *, tenant_id: UUID | None, include_all: bool = False) -> list[Payment]:
        if tenant_id is not None:
            await set_tenant_context(self.db, str(tenant_id))

        query = select(Payment).order_by(Payment.created_at.desc())
        if tenant_id is not None and not include_all:
            query = query.where(Payment.tenant_id == tenant_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_payment(self, payment_id: UUID) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    def verify_stripe_event(self, payload: bytes, signature_header: str) -> stripe.Event:
        # Stripe requires the exact raw body bytes; parsing before verification breaks signatures.
        secret = self._get_stripe_webhook_secret()
        try:
            return stripe.Webhook.construct_event(payload, signature_header, secret)
        except ValueError as exc:
            raise APIError(400, ErrorCode.BAD_REQUEST, "Invalid Stripe webhook payload") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise APIError(400, ErrorCode.BAD_REQUEST, "Invalid Stripe webhook signature") from exc

    async def process_stripe_event(self, event: Any) -> StripeEventResult:
        event_id = _stripe_value(event, "id")
        event_type = _stripe_value(event, "type")
        payment_intent = _stripe_nested_object(event)
        payment_intent_id = _stripe_value(payment_intent, "id", default=None)

        existing_event = await self.db.get(StripeWebhookEvent, event_id)
        if existing_event is not None:
            return StripeEventResult(
                event_id=event_id,
                event_type=event_type,
                payment_intent_id=existing_event.payment_intent_id,
                duplicate=True,
                status=None,
            )

        status = _status_from_event_type(event_type)
        if status and payment_intent_id:
            await self._upsert_payment_from_webhook(payment_intent=payment_intent, status=status)

        self.db.add(
            StripeWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payment_intent_id=payment_intent_id,
            )
        )
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            return StripeEventResult(event_id=event_id, event_type=event_type, payment_intent_id=payment_intent_id, duplicate=True)

        if event_type == "payment_intent.succeeded" and payment_intent_id:
            await self._emit_signed_payment_notification(payment_intent=payment_intent)

        logger.info(
            "payment.stripe_webhook_processed",
            extra={"event": "payment.stripe_webhook_processed", "stripe_event_id": event_id, "stripe_event_type": event_type},
        )
        return StripeEventResult(event_id=event_id, event_type=event_type, payment_intent_id=payment_intent_id, status=status)

    async def _create_stripe_payment_intent(self, *, amount: int, currency: str, metadata: dict[str, str]) -> Any:
        secret_key = self._get_stripe_secret_key()
        if secret_key == LAB_STRIPE_SECRET_PLACEHOLDER:
            # Lab fallback keeps local tests/demo usable when no Stripe sandbox key has been injected.
            return {
                "id": f"pi_lab_{uuid4().hex}",
                "client_secret": f"pi_lab_secret_{uuid4().hex}",
                "status": "requires_payment_method",
            }

        def create() -> Any:
            return stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
                api_key=secret_key,
            )

        return await anyio.to_thread.run_sync(create)

    async def _upsert_payment_from_webhook(self, *, payment_intent: Any, status: str) -> None:
        payment_intent_id = _stripe_value(payment_intent, "id")
        result = await self.db.execute(select(Payment).where(Payment.stripe_payment_intent_id == payment_intent_id))
        payment = result.scalar_one_or_none()
        metadata = _stripe_value(payment_intent, "metadata", default={}) or {}

        if payment is None:
            tenant_id = metadata.get("tenant_id")
            user_id = metadata.get("user_id")
            if not tenant_id or not user_id:
                logger.warning(
                    "payment.stripe_webhook_unmatched",
                    extra={"event": "payment.stripe_webhook_unmatched", "payment_intent_id": payment_intent_id},
                )
                return

            payment = Payment(
                id=uuid4(),
                tenant_id=UUID(str(tenant_id)),
                user_id=str(user_id),
                stripe_payment_intent_id=payment_intent_id,
                amount=int(_stripe_value(payment_intent, "amount", default=0)),
                currency=str(_stripe_value(payment_intent, "currency", default="usd")).lower(),
                status=status,
            )
            self.db.add(payment)
            return

        payment.status = status

    async def _emit_signed_payment_notification(self, *, payment_intent: Any) -> None:
        payment_intent_id = _stripe_value(payment_intent, "id")
        metadata = _stripe_value(payment_intent, "metadata", default={}) or {}
        payload = {
            "event": "payment.succeeded",
            "payment_intent_id": payment_intent_id,
            "amount": int(_stripe_value(payment_intent, "amount", default=0)),
            "tenant_id": metadata.get("tenant_id"),
        }

        try:
            signer = self._get_webhook_signer()
            headers = create_webhook_signature_headers(payload, signer=signer)
        except Exception as exc:
            logger.warning(
                "payment.outbound_webhook_signing_unavailable",
                extra={"event": "payment.outbound_webhook_signing_unavailable", "payment_intent_id": payment_intent_id},
            )
            return

        logger.info(
            "payment.outbound_webhook_signed",
            extra={
                "event": "payment.outbound_webhook_signed",
                "payment_intent_id": payment_intent_id,
                "tenant_id": payload["tenant_id"],
                "X-Webhook-Algorithm": headers["X-Webhook-Algorithm"],
                "X-Webhook-Signature": headers["X-Webhook-Signature"],
            },
        )

    def _get_webhook_signer(self) -> MLDSASigner:
        if self._webhook_signer is None:
            self._webhook_signer = MLDSASigner.from_vault(self._get_vault_client(), key_path=WEBHOOK_SIGNING_KEY_PATH)
        return self._webhook_signer

    def _get_stripe_secret_key(self) -> str:
        if self._stripe_secret_key is None:
            self._stripe_secret_key = self._read_secret(STRIPE_SECRET_KEY_PATH, env_name="STRIPE_SECRET_KEY", default=LAB_STRIPE_SECRET_PLACEHOLDER)
        return self._stripe_secret_key

    def _get_stripe_webhook_secret(self) -> str:
        if self._stripe_webhook_secret is None:
            self._stripe_webhook_secret = self._read_secret(
                STRIPE_WEBHOOK_SECRET_PATH,
                env_name="STRIPE_WEBHOOK_SECRET",
                default=LAB_STRIPE_WEBHOOK_PLACEHOLDER,
            )
        return self._stripe_webhook_secret

    def _read_secret(self, path: str, *, env_name: str, default: str) -> str:
        try:
            return str(self._get_vault_client().get_secret(path))
        except Exception:
            env_value = os.getenv(env_name)
            if env_value:
                return env_value
            return default

    def _get_vault_client(self) -> VaultClient:
        if self._vault_client is not None:
            return self._vault_client

        role_id = os.getenv("VAULT_ROLE_ID") or os.getenv("PAYMENT_SVC_VAULT_ROLE_ID")
        secret_id = os.getenv("VAULT_SECRET_ID") or os.getenv("PAYMENT_SVC_VAULT_SECRET_ID")
        if role_id and secret_id:
            self._vault_client = VaultClient.from_approle(role_id=role_id, secret_id=secret_id)
            return self._vault_client

        token = os.getenv("VAULT_TOKEN") or os.getenv("VAULT_DEV_TOKEN")
        if token:
            self._vault_client = VaultClient(token=token)
            return self._vault_client

        self._vault_client = VaultClient()
        return self._vault_client


def _stripe_value(obj: Any, key: str, *, default: Any = ...):
    if isinstance(obj, dict):
        value = obj.get(key, default)
    else:
        value = getattr(obj, key, default)
        if value is default and hasattr(obj, "get"):
            value = obj.get(key, default)
    if value is ...:
        raise APIError(400, ErrorCode.BAD_REQUEST, f"Stripe object missing field: {key}")
    return value


def _stripe_nested_object(event: Any) -> Any:
    data = _stripe_value(event, "data")
    return _stripe_value(data, "object")


def _status_from_event_type(event_type: str) -> str | None:
    if event_type == "payment_intent.succeeded":
        return "succeeded"
    if event_type == "payment_intent.payment_failed":
        return "failed"
    return None
