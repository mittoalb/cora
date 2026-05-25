# pyright: reportPrivateUsage=false

"""Unit tests for `cora.infrastructure.idempotency_pruner`.

Pins the lifespan task's three behavioral surfaces:
  - Skip branches: `ttl_hours <= 0` AND `pool is None` both yield
    a no-op context manager (background task never spawned).
  - Loop body: periodically calls `store.prune(ttl_hours=...)`,
    log-emits when rows were deleted.
  - Failure recovery: a failing `prune()` call is logged and the
    loop continues — only `CancelledError` (lifespan shutdown)
    breaks the loop.

The pruner code path is brand-new and would otherwise have ZERO
test coverage; see the idempotency gate review for the rationale.
"""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.idempotency_pruner import idempotency_pruner_lifespan
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FakeClock,
    FixedIdGenerator,
)
from cora.infrastructure.ports.idempotency_store import ClaimOutcome


def _build_kernel(
    *,
    ttl_hours: int = 24,
    pool: object | None = "fake-pool",
    store: InMemoryIdempotencyStore | None = None,
) -> Kernel:
    """Build a Kernel for pruner tests. `pool` defaults to a sentinel
    string (not None) so the pruner's "no pool" skip branch isn't
    accidentally triggered by every test; pass `pool=None` to opt in."""
    return make_inmemory_kernel(
        settings=Settings(  # type: ignore[call-arg]
            app_env="test",
            idempotency_ttl_hours=ttl_hours,
        ),
        clock=FakeClock(datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
        idempotency_store=store,
        pool=pool,
    )


@pytest.mark.unit
async def test_lifespan_skips_when_ttl_hours_is_zero() -> None:
    """ttl_hours=0 disables the pruner entirely (forensic-deployment
    opt-out). The background task must never be spawned, so calling
    prune() during the lifespan would NOT be observable."""
    pruned_calls: list[int] = []

    class _CountingStore(InMemoryIdempotencyStore):
        async def prune(self, *, ttl_hours: int) -> int:
            pruned_calls.append(ttl_hours)
            return 0

    store = _CountingStore()
    deps = _build_kernel(ttl_hours=0, store=store)
    async with idempotency_pruner_lifespan(deps, interval_seconds=0.01):
        await asyncio.sleep(0.05)  # plenty of time for a tick if it were running
    assert pruned_calls == []


@pytest.mark.unit
async def test_lifespan_skips_when_pool_is_none() -> None:
    """In the in-memory test environment (`pool=None`) there's no DB
    to prune against. The pruner skips."""
    pruned_calls: list[int] = []

    class _CountingStore(InMemoryIdempotencyStore):
        async def prune(self, *, ttl_hours: int) -> int:
            pruned_calls.append(ttl_hours)
            return 0

    store = _CountingStore()
    deps = _build_kernel(ttl_hours=24, pool=None, store=store)
    async with idempotency_pruner_lifespan(deps, interval_seconds=0.01):
        await asyncio.sleep(0.05)
    assert pruned_calls == []


@pytest.mark.unit
async def test_lifespan_calls_prune_periodically_with_configured_ttl() -> None:
    """The active path: pruner spawns a task that calls store.prune
    with the Settings-configured ttl_hours on every interval tick."""
    pruned_calls: list[int] = []
    tick = asyncio.Event()

    class _CountingStore(InMemoryIdempotencyStore):
        async def prune(self, *, ttl_hours: int) -> int:
            pruned_calls.append(ttl_hours)
            tick.set()
            return 0

    store = _CountingStore()
    deps = _build_kernel(ttl_hours=12, store=store)
    async with idempotency_pruner_lifespan(deps, interval_seconds=0.01):
        # Wait for at least one prune call (race-safe: tick.set() in prune).
        await asyncio.wait_for(tick.wait(), timeout=1.0)
    assert pruned_calls
    assert all(t == 12 for t in pruned_calls)


@pytest.mark.unit
async def test_lifespan_loop_survives_transient_prune_failure() -> None:
    """Contract: a failing prune call is logged and the loop
    continues, so transient DB hiccups don't kill the pruner.
    Without this, one bad prune call would silently disable cleanup
    for the rest of the process lifetime."""
    pruned_calls: list[int] = []
    succeeded = asyncio.Event()

    class _FlakyStore(InMemoryIdempotencyStore):
        async def prune(self, *, ttl_hours: int) -> int:
            pruned_calls.append(ttl_hours)
            if len(pruned_calls) == 1:
                raise RuntimeError("simulated db hiccup")
            succeeded.set()
            return 0

    store = _FlakyStore()
    deps = _build_kernel(ttl_hours=24, store=store)
    async with idempotency_pruner_lifespan(deps, interval_seconds=0.01):
        await asyncio.wait_for(succeeded.wait(), timeout=1.0)
    # First call raised, second call succeeded — loop survived.
    assert len(pruned_calls) >= 2


@pytest.mark.unit
async def test_lifespan_cancels_loop_cleanly_on_exit() -> None:
    """On lifespan exit the background task gets cancelled and the
    teardown awaits it. Verify by re-entering a second lifespan
    after the first exits — if cleanup were broken (task leaked),
    the second lifespan's task would race with the first's."""
    deps = _build_kernel(ttl_hours=24)

    async with idempotency_pruner_lifespan(deps, interval_seconds=0.01):
        await asyncio.sleep(0.02)
    # If we get here without a hang or stray task error, teardown worked.
    # Re-enter to confirm clean state.
    async with idempotency_pruner_lifespan(deps, interval_seconds=0.01):
        await asyncio.sleep(0.02)


@pytest.mark.unit
async def test_lifespan_real_inmemory_store_drops_expired_row_end_to_end() -> None:
    """Wider integration-flavored unit test: seed an actually-expired
    row in the in-memory store, run the pruner with a tight tick,
    assert the row is gone. End-to-end exercise of the lifespan +
    loop + adapter prune path."""
    from datetime import timedelta

    from cora.infrastructure.adapters.in_memory_idempotency_store import _Row

    store = InMemoryIdempotencyStore()
    # Seed one expired completed row + one fresh completed row.
    surface = UUID("00000000-0000-0000-0000-000000000020")
    expired_key = (UUID(int=1), "expired", surface)
    fresh_key = (UUID(int=2), "fresh", surface)
    now = datetime.now(tz=UTC)
    store._records[expired_key] = _Row(  # pyright: ignore[reportPrivateUsage]
        command_hash="h",
        command_name="X",
        created_at=now - timedelta(hours=48),
        result="x",
    )
    store._records[fresh_key] = _Row(  # pyright: ignore[reportPrivateUsage]
        command_hash="h",
        command_name="X",
        created_at=now,
        result="x",
    )

    deps = _build_kernel(ttl_hours=24, store=store)
    async with idempotency_pruner_lifespan(deps, interval_seconds=0.01):
        # Poll until the expired row is gone (race-safe; up to 1s).
        for _ in range(100):
            if expired_key not in store._records:  # pyright: ignore[reportPrivateUsage]
                break
            await asyncio.sleep(0.01)

    assert expired_key not in store._records  # pyright: ignore[reportPrivateUsage]
    assert fresh_key in store._records  # pyright: ignore[reportPrivateUsage]


# Suppress unused imports flagged by ruff that are referenced in the
# `_build_kernel` helper indirectly via type annotations and helpers.
_ = (Any, ClaimOutcome, replace)
