#!/usr/bin/env python
"""Generate ML-DSA-65 keypairs and store them in Vault KV v2."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.pqc_signing import (  # noqa: E402
    ML_DSA_ALGORITHM,
    S2S_SIGNING_KEY_PATH,
    WEBHOOK_SIGNING_KEY_PATH,
    generate_mldsa_keypair_secret,
    key_sizes,
)
from shared.vault_client import VaultClient  # noqa: E402


DEFAULT_VAULT_ADDR = "http://localhost:8200"
DEFAULT_VAULT_TOKEN = "root-token-for-lab-only"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate real ML-DSA-65 keys for the lab.")
    parser.add_argument(
        "--vault-addr",
        default=os.getenv("VAULT_ADDR", DEFAULT_VAULT_ADDR),
        help="Vault address reachable from the host.",
    )
    parser.add_argument(
        "--vault-token",
        default=os.getenv("VAULT_TOKEN") or os.getenv("VAULT_DEV_TOKEN") or DEFAULT_VAULT_TOKEN,
        help="Vault token with write access to secret/data/pqc/*.",
    )
    parser.add_argument("--mount-point", default="secret", help="Vault KV v2 mount point.")
    parser.add_argument(
        "--key-path",
        action="append",
        dest="key_paths",
        help="KV path to write. May be repeated. Defaults to S2S and webhook signing keys.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key_paths = args.key_paths or [S2S_SIGNING_KEY_PATH, WEBHOOK_SIGNING_KEY_PATH]
    vault = VaultClient(addr=args.vault_addr, token=args.vault_token)
    sizes = key_sizes()

    for key_path in key_paths:
        secret = generate_mldsa_keypair_secret()
        vault.put_secret(key_path, secret, mount_point=args.mount_point)
        print(
            "stored "
            f"{args.mount_point}/{key_path} "
            f"algorithm={ML_DSA_ALGORITHM} "
            f"public_key_bytes={sizes['public_key_bytes']} "
            f"private_key_bytes={sizes['private_key_bytes']} "
            f"signature_bytes={sizes['signature_bytes']}"
        )

    print("ML-DSA private keys were written to Vault only and were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
