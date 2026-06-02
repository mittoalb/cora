"""Worker honors per-subscriber `batch_size` (Reaction = 1, Projection = 100).

Pins the behavior added when `Reaction` Protocol shipped: the worker
reads `batch_size` from each Subscriber via `getattr` and passes it
to `advance_subscriber_once`. Existing Projections that pre-date the
attribute fall back to the worker-level default.
"""

# pyright: reportPrivateUsage=false

import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from cora.infrastructure.projection.handler import DEFAULT_BATCH_SIZE
from cora.infrastructure.projection.registry import ProjectionRegistry
from cora.infrastructure.projection.wakeup import PollOnlyWakeup
from cora.infrastructure.projection.worker import ProjectionWorker


class _ReactionLike:
    """Probe Subscriber with `batch_size = 1` (the Reaction convention)."""

    name = "probe_reaction"
    subscribed_event_types = frozenset({"DummyEvent"})
    batch_size = 1

    async def apply(self, event: Any, conn: Any) -> None: ...


class _ProjectionLike:
    """Probe Subscriber WITHOUT a `batch_size` attribute, simulating a
    pre-existing Projection that pre-dates per-subscriber tuning."""

    name = "probe_projection"
    subscribed_event_types = frozenset({"DummyEvent"})

    async def apply(self, event: Any, conn: Any) -> None: ...


class _ProjectionWithBatch:
    """Probe Projection that declares a custom `batch_size`."""

    name = "probe_projection_explicit"
    subscribed_event_types = frozenset({"DummyEvent"})
    batch_size = 250

    async def apply(self, event: Any, conn: Any) -> None: ...


async def _run_one_iteration(worker: ProjectionWorker, subscriber: Any) -> None:
    """Drive a single advance iteration of the worker's loop without
    running forever. The mocked `advance_subscriber_once` returns 0
    immediately so the loop goes to `wakeup.wait`; we never get
    there because we cancel before then."""
    loop_task = asyncio.create_task(worker._advance_loop(subscriber))
    await asyncio.sleep(0.05)
    loop_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await loop_task


@pytest.mark.asyncio
async def test_worker_reads_reaction_batch_size_one() -> None:
    """A Subscriber that declares `batch_size = 1` is advanced with
    batch_size=1, regardless of the worker-level default."""
    registry = ProjectionRegistry()
    reaction = _ReactionLike()
    registry.register(reaction)

    worker = ProjectionWorker(
        pool=AsyncMock(),
        registry=registry,
        wakeup=PollOnlyWakeup(),
        poll_interval_seconds=10.0,
        batch_size=DEFAULT_BATCH_SIZE,
    )

    advance = AsyncMock(return_value=0)
    with patch(
        "cora.infrastructure.projection.worker.advance_subscriber_once",
        advance,
    ):
        await _run_one_iteration(worker, reaction)

    assert advance.called
    _, kwargs = advance.call_args
    assert kwargs["batch_size"] == 1, (
        f"Expected reaction.batch_size=1 to be passed, got {kwargs['batch_size']}"
    )


@pytest.mark.asyncio
async def test_worker_falls_back_to_default_when_subscriber_omits_batch_size() -> None:
    """A Subscriber that does NOT declare `batch_size` falls back to
    the worker-level default. Backward compatibility for the 14
    Projections that pre-date the per-subscriber knob."""
    registry = ProjectionRegistry()
    projection = _ProjectionLike()
    registry.register(projection)

    worker = ProjectionWorker(
        pool=AsyncMock(),
        registry=registry,
        wakeup=PollOnlyWakeup(),
        poll_interval_seconds=10.0,
        batch_size=DEFAULT_BATCH_SIZE,
    )

    advance = AsyncMock(return_value=0)
    with patch(
        "cora.infrastructure.projection.worker.advance_subscriber_once",
        advance,
    ):
        await _run_one_iteration(worker, projection)

    assert advance.called
    _, kwargs = advance.call_args
    assert kwargs["batch_size"] == DEFAULT_BATCH_SIZE


@pytest.mark.asyncio
async def test_worker_honors_explicit_projection_batch_size() -> None:
    """A Projection that overrides `batch_size` (e.g., to 250 for a
    high-throughput projection) wins over the worker-level default."""
    registry = ProjectionRegistry()
    projection = _ProjectionWithBatch()
    registry.register(projection)

    worker = ProjectionWorker(
        pool=AsyncMock(),
        registry=registry,
        wakeup=PollOnlyWakeup(),
        poll_interval_seconds=10.0,
        batch_size=DEFAULT_BATCH_SIZE,
    )

    advance = AsyncMock(return_value=0)
    with patch(
        "cora.infrastructure.projection.worker.advance_subscriber_once",
        advance,
    ):
        await _run_one_iteration(worker, projection)

    assert advance.called
    _, kwargs = advance.call_args
    assert kwargs["batch_size"] == 250
