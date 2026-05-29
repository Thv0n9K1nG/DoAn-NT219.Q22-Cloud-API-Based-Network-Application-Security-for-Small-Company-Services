"""ML-DSA-65 signing primitives backed by Vault-managed key material."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from pqcrypto.sign import ml_dsa_65

from shared.vault_client import VaultClient


ML_DSA_ALGORITHM = "ML-DSA-65"
DEFAULT_KV_MOUNT = "secret"
S2S_SIGNING_KEY_PATH = "pqc/s2s-signing"
WEBHOOK_SIGNING_KEY_PATH = "pqc/webhook-signing"


class PQCKeyError(RuntimeError):
    """Raised when ML-DSA key material is absent, malformed, or unusable."""


@dataclass(frozen=True)
class MLDSAKeyPair:
    """Base64-encoded ML-DSA-65 keypair suitable for Vault KV storage."""

    public_key: str
    private_key: str
    algorithm: str = ML_DSA_ALGORITHM

    @classmethod
    def generate(cls) -> "MLDSAKeyPair":
        public_key, private_key = ml_dsa_65.generate_keypair()
        return cls(
            public_key=base64.b64encode(public_key).decode("ascii"),
            private_key=base64.b64encode(private_key).decode("ascii"),
        )

    def as_secret(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "public_key": self.public_key,
            "private_key": self.private_key,
        }


class MLDSASigner:
    """Sign and verify payloads with ML-DSA-65 keys loaded from Vault KV."""

    def __init__(
        self,
        *,
        vault: VaultClient | None = None,
        key_path: str = S2S_SIGNING_KEY_PATH,
        mount_point: str = DEFAULT_KV_MOUNT,
        public_key: bytes | None = None,
        private_key: bytes | None = None,
    ):
        self.key_path = key_path
        self.mount_point = mount_point
        self._public_key = public_key
        self._private_key = private_key

        if vault is not None:
            self._load_from_vault(vault)

    @classmethod
    def from_vault(
        cls,
        vault: VaultClient,
        *,
        key_path: str = S2S_SIGNING_KEY_PATH,
        mount_point: str = DEFAULT_KV_MOUNT,
    ) -> "MLDSASigner":
        return cls(vault=vault, key_path=key_path, mount_point=mount_point)

    @classmethod
    def from_keypair(cls, keypair: MLDSAKeyPair) -> "MLDSASigner":
        return cls(
            public_key=_decode_key_b64(keypair.public_key, "public_key"),
            private_key=_decode_key_b64(keypair.private_key, "private_key"),
        )

    @property
    def public_key_size(self) -> int:
        self._require_public_key()
        return len(self._public_key or b"")

    @property
    def private_key_size(self) -> int:
        self._require_private_key()
        return len(self._private_key or b"")

    def sign(self, payload: bytes) -> str:
        """Return a standard base64 ML-DSA signature for the exact payload bytes."""

        private_key = self._require_private_key()
        signature = ml_dsa_65.sign(private_key, payload)
        return base64.b64encode(signature).decode("ascii")

    def verify(self, payload: bytes, signature_b64: str) -> bool:
        """Verify a standard base64 ML-DSA signature without raising on bad input."""

        public_key = self._require_public_key()
        try:
            signature = base64.b64decode(signature_b64, validate=True)
        except Exception:
            return False

        try:
            return bool(ml_dsa_65.verify(public_key, payload, signature))
        except Exception:
            return False

    def _load_from_vault(self, vault: VaultClient) -> None:
        secret = vault.get_secret_dict(self.key_path, mount_point=self.mount_point)
        algorithm = secret.get("algorithm")
        if algorithm != ML_DSA_ALGORITHM:
            raise PQCKeyError(f"Unsupported PQC key algorithm at {self.key_path}: {algorithm!r}")

        self._public_key = _decode_key_b64(secret.get("public_key"), "public_key")
        self._private_key = _decode_key_b64(secret.get("private_key"), "private_key")
        _validate_key_sizes(self._public_key, self._private_key, self.key_path)

    def _require_public_key(self) -> bytes:
        if self._public_key is None:
            raise PQCKeyError("ML-DSA public key is not loaded")
        if len(self._public_key) != ml_dsa_65.PUBLIC_KEY_SIZE:
            raise PQCKeyError("ML-DSA public key has an invalid size")
        return self._public_key

    def _require_private_key(self) -> bytes:
        if self._private_key is None:
            raise PQCKeyError("ML-DSA private key is not loaded")
        if len(self._private_key) != ml_dsa_65.SECRET_KEY_SIZE:
            raise PQCKeyError("ML-DSA private key has an invalid size")
        return self._private_key


def generate_mldsa_keypair_secret() -> dict[str, str]:
    """Generate a fresh ML-DSA-65 keypair encoded for Vault KV v2."""

    return MLDSAKeyPair.generate().as_secret()


def key_sizes() -> dict[str, int]:
    return {
        "public_key_bytes": ml_dsa_65.PUBLIC_KEY_SIZE,
        "private_key_bytes": ml_dsa_65.SECRET_KEY_SIZE,
        "signature_bytes": ml_dsa_65.SIGNATURE_SIZE,
    }


def _decode_key_b64(value: Any, field_name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise PQCKeyError(f"Missing ML-DSA {field_name}")
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise PQCKeyError(f"Invalid base64 for ML-DSA {field_name}") from exc


def _validate_key_sizes(public_key: bytes, private_key: bytes, key_path: str) -> None:
    if len(public_key) != ml_dsa_65.PUBLIC_KEY_SIZE:
        raise PQCKeyError(f"Invalid public key size at {key_path}: {len(public_key)}")
    if len(private_key) != ml_dsa_65.SECRET_KEY_SIZE:
        raise PQCKeyError(f"Invalid private key size at {key_path}: {len(private_key)}")
