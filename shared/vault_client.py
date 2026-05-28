"""Small Vault wrapper for service bootstrap, KV v2, Transit, and PKI."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import hvac

from shared.config import get_settings


@dataclass(frozen=True)
class VaultCertificate:
    certificate: str
    private_key: str
    issuing_ca: str | None = None
    serial_number: str | None = None


class VaultClient:
    """Wrap hvac calls behind project-specific paths and tenant key names."""

    def __init__(
        self,
        *,
        addr: str | None = None,
        token: str | None = None,
        client: hvac.Client | None = None,
    ):
        settings = get_settings()
        self.client = client or hvac.Client(url=addr or settings.vault_addr, token=token)

    @classmethod
    def from_approle(cls, *, role_id: str, secret_id: str, addr: str | None = None) -> "VaultClient":
        vault = cls(addr=addr)
        vault.authenticate_approle(role_id=role_id, secret_id=secret_id)
        return vault

    @classmethod
    def from_env(cls) -> "VaultClient":
        settings = get_settings()
        if not settings.vault_role_id or not settings.vault_secret_id:
            raise RuntimeError("VAULT_ROLE_ID and VAULT_SECRET_ID are required for AppRole authentication")
        return cls.from_approle(
            role_id=settings.vault_role_id,
            secret_id=settings.vault_secret_id,
            addr=settings.vault_addr,
        )

    def authenticate_approle(self, *, role_id: str, secret_id: str) -> None:
        response = self.client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        token = response["auth"]["client_token"]
        self.client.token = token

    def get_secret_dict(self, path: str, *, mount_point: str = "secret") -> dict[str, Any]:
        response = self.client.secrets.kv.v2.read_secret_version(
            path=self._clean_kv_path(path),
            mount_point=mount_point,
            raise_on_deleted_version=True,
        )
        return response["data"]["data"]

    def get_secret(self, path: str, key: str = "value", *, mount_point: str = "secret") -> Any:
        secret = self.get_secret_dict(path, mount_point=mount_point)
        return secret[key]

    def put_secret(self, path: str, data: dict[str, Any], *, mount_point: str = "secret") -> None:
        # Admin/setup scripts use this method; service AppRole policies intentionally do not grant it.
        self.client.secrets.kv.v2.create_or_update_secret(
            path=self._clean_kv_path(path),
            secret=data,
            mount_point=mount_point,
        )

    def encrypt(self, tenant_id: str, plaintext: bytes | str, *, mount_point: str = "transit") -> str:
        raw = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
        response = self.client.secrets.transit.encrypt_data(
            name=self._tenant_key_name(tenant_id),
            plaintext=base64.b64encode(raw).decode("ascii"),
            mount_point=mount_point,
        )
        return response["data"]["ciphertext"]

    def decrypt(self, tenant_id: str, ciphertext: str, *, mount_point: str = "transit") -> bytes:
        response = self.client.secrets.transit.decrypt_data(
            name=self._tenant_key_name(tenant_id),
            ciphertext=ciphertext,
            mount_point=mount_point,
        )
        return base64.b64decode(response["data"]["plaintext"])

    def issue_certificate(
        self,
        common_name: str,
        *,
        role: str = "internal-services",
        ttl: str = "24h",
        mount_point: str = "pki",
    ) -> VaultCertificate:
        response = self.client.secrets.pki.generate_certificate(
            name=role,
            common_name=common_name,
            ttl=ttl,
            mount_point=mount_point,
        )
        data = response["data"]
        return VaultCertificate(
            certificate=data["certificate"],
            private_key=data["private_key"],
            issuing_ca=data.get("issuing_ca"),
            serial_number=data.get("serial_number"),
        )

    @staticmethod
    def _tenant_key_name(tenant_id: str) -> str:
        return f"tenant-{tenant_id}"

    @staticmethod
    def _clean_kv_path(path: str) -> str:
        return path.removeprefix("secret/").removeprefix("data/").strip("/")
