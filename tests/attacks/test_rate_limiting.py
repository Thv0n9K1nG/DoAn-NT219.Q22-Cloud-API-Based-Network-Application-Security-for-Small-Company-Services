from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FixedWindowRateLimiter:
    """Model Kong's minute quota so attack tests can assert deterministic 429 behavior."""

    limit_per_window: int
    counters: dict[tuple[str, int], int] = field(default_factory=dict)

    def allow(self, identity: str, *, now_seconds: int) -> bool:
        window = now_seconds // 60
        key = (identity, window)
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key] <= self.limit_per_window


def test_rate_limit_returns_429_after_configured_minute_quota():
    limiter = FixedWindowRateLimiter(limit_per_window=20)
    status_codes = [200 if limiter.allow("tenant-alpha", now_seconds=1000) else 429 for _ in range(25)]

    assert status_codes[:20] == [200] * 20
    assert status_codes[20:] == [429] * 5


def test_rate_limit_counter_is_isolated_by_identity():
    limiter = FixedWindowRateLimiter(limit_per_window=2)

    assert [limiter.allow("tenant-alpha", now_seconds=1000) for _ in range(3)] == [True, True, False]
    assert [limiter.allow("tenant-beta", now_seconds=1000) for _ in range(2)] == [True, True]
