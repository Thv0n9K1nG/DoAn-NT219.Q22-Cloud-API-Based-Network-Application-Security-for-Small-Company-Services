#!/usr/bin/env python
"""Measure ML-DSA-65 key generation, signing, and verification latency."""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.pqc_signing import MLDSAKeyPair, MLDSASigner, key_sizes  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark ML-DSA-65 operations.")
    parser.add_argument("--iterations", type=int, default=100, help="Number of sign/verify iterations.")
    parser.add_argument("--message-size", type=int, default=256, help="Payload size in bytes.")
    return parser.parse_args()


def percentile(values: list[float], percentile_value: float) -> float:
    values = sorted(values)
    index = int(round((percentile_value / 100) * (len(values) - 1)))
    return values[index]


def main() -> int:
    args = parse_args()
    message = b"x" * args.message_size

    start = time.perf_counter()
    keypair = MLDSAKeyPair.generate()
    keygen_ms = (time.perf_counter() - start) * 1000
    signer = MLDSASigner.from_keypair(keypair)

    sign_times: list[float] = []
    verify_times: list[float] = []
    signatures: list[str] = []

    for _ in range(args.iterations):
        start = time.perf_counter()
        signature = signer.sign(message)
        sign_times.append((time.perf_counter() - start) * 1000)
        signatures.append(signature)

        start = time.perf_counter()
        verified = signer.verify(message, signature)
        verify_times.append((time.perf_counter() - start) * 1000)
        if not verified:
            raise RuntimeError("ML-DSA verification failed during benchmark")

    sizes = key_sizes()
    print("ML-DSA-65 benchmark")
    print(f"iterations={args.iterations}")
    print(f"message_size_bytes={args.message_size}")
    print(f"keygen_ms={keygen_ms:.3f}")
    print(f"sign_p50_ms={statistics.median(sign_times):.3f}")
    print(f"sign_p95_ms={percentile(sign_times, 95):.3f}")
    print(f"verify_p50_ms={statistics.median(verify_times):.3f}")
    print(f"verify_p95_ms={percentile(verify_times, 95):.3f}")
    print(f"signature_bytes={sizes['signature_bytes']}")
    print(f"public_key_bytes={sizes['public_key_bytes']}")
    print(f"private_key_bytes={sizes['private_key_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
