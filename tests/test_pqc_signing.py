from __future__ import annotations

import base64

import pytest

from shared.pqc_signing import (
    ML_DSA_ALGORITHM,
    PQCKeyError,
    S2S_SIGNING_KEY_PATH,
    MLDSAKeyPair,
    MLDSASigner,
    key_sizes,
)


class FakeVault:
    def __init__(self, secret):
        self.secret = secret

    def get_secret_dict(self, path: str, *, mount_point: str = "secret"):
        assert path == S2S_SIGNING_KEY_PATH
        assert mount_point == "secret"
        return self.secret


def test_mldsa_sign_and_verify_from_vault_secret():
    keypair = MLDSAKeyPair.generate()
    signer = MLDSASigner.from_vault(FakeVault(keypair.as_secret()))

    payload = b"stage-12-pqc-payload"
    signature = signer.sign(payload)

    assert signer.verify(payload, signature) is True
    assert signer.verify(b"tampered", signature) is False
    assert signer.verify(payload, "not valid base64!") is False


def test_mldsa_rejects_missing_or_malformed_keys():
    valid_public_key = MLDSAKeyPair.generate().public_key
    with pytest.raises(PQCKeyError, match="Missing ML-DSA private_key"):
        MLDSASigner.from_vault(FakeVault({"algorithm": ML_DSA_ALGORITHM, "public_key": valid_public_key}))

    with pytest.raises(PQCKeyError, match="Invalid base64"):
        MLDSASigner.from_vault(
            FakeVault({"algorithm": ML_DSA_ALGORITHM, "public_key": "not-base64", "private_key": "not-base64"})
        )


def test_mldsa_rejects_placeholder_or_wrong_size_keys():
    secret = {
        "algorithm": ML_DSA_ALGORITHM,
        "public_key": base64.b64encode(b"placeholder-public").decode("ascii"),
        "private_key": base64.b64encode(b"placeholder-private").decode("ascii"),
    }

    with pytest.raises(PQCKeyError, match="Invalid public key size"):
        MLDSASigner.from_vault(FakeVault(secret))


def test_generated_key_sizes_match_mldsa65_constants():
    signer = MLDSASigner.from_keypair(MLDSAKeyPair.generate())
    sizes = key_sizes()

    assert signer.public_key_size == sizes["public_key_bytes"] == 1952
    assert signer.private_key_size == sizes["private_key_bytes"] == 4032
    assert sizes["signature_bytes"] == 3309
