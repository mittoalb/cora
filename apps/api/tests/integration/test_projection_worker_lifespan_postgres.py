"""End-to-end: ProjectionWorker.run() advances projections without
manual `drain_projections` calls.

Closes M4 from the 8e-1b gate review: prior integration tests
exercise `advance_subscriber_once` via the synchronous
`drain_projections` helper, but the worker's actual
`asyncio.TaskGroup` loop + `WakeupSource` integration + cancellation
plumbing was untested end-to-end.

Modern asyncio test pattern: `asyncio.timeout(...)` wraps a polling
loop that selects from the projection table until the row appears
(eventual-consistency wait). Intentionally not using an
`asyncio.Event` hook on `apply()` — that fires INSIDE the worker's
transaction, before commit; querying the proj table from another
connection at that point sees nothing. Polling for the committed row
is the right shape here.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register
from cora.access.projections.summary import ActorSummaryProjection
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.infrastructure.projection import ProjectionRegistry
from cora.infrastructure.projection.wakeup import PollOnlyWakeup
from cora.infrastructure.projection.worker import ProjectionWorker

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(ids),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
        pool=db_pool,
    )


async def _wait_for_row(
    pool: asyncpg.Pool,
    actor_id: UUID,
    *,
    deadline_seconds: float = 5.0,
    poll_interval_seconds: float = 0.05,
) -> Any:
    """Poll the proj table until the row exists or the deadline
    expires. asyncio.TimeoutError on miss surfaces clearly in the
    test report; clean alternative to inflexible `sleep + assert`."""
    async with asyncio.timeout(deadline_seconds):
        while True:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT name, status FROM proj_access_actor_summary WHERE actor_id = $1",
                    actor_id,
                )
            if row is not None:
                return row
            await asyncio.sleep(poll_interval_seconds)


@pytest.mark.integration
async def test_worker_run_processes_events_until_cancelled(
    db_pool: asyncpg.Pool,
) -> None:
    """Append an event, spawn ProjectionWorker.run() as a task, poll
    for the proj row to commit, assert it has the expected state,
    cancel the task cleanly."""
    actor_id = uuid4()
    event_id = uuid4()
    deps = _build_deps(db_pool, [actor_id, event_id])

    await bind_register(deps)(
        RegisterActor(name="WorkerTest"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    registry.register(ActorSummaryProjection())

    # PollOnlyWakeup with a short interval so the worker tries an
    # advance batch quickly even without LISTEN/NOTIFY (test
    # determinism > production latency).
    worker = ProjectionWorker(
        db_pool,
        registry,
        PollOnlyWakeup(),
        poll_interval_seconds=0.1,
    )

    task = asyncio.create_task(worker.run(), name="test-projection-worker")
    try:
        row = await _wait_for_row(db_pool, actor_id, deadline_seconds=5.0)
        assert row["name"] == "WorkerTest"
        assert row["status"] == "active"
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, BaseExceptionGroup):
            await task


@pytest.mark.integration
async def test_worker_cancellation_is_clean(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: cancelling the worker task surfaces as CancelledError /
    BaseExceptionGroup containing only CancelledError. No spurious
    exceptions, no resource leaks. TaskGroup contract preserved."""
    registry = ProjectionRegistry()
    registry.register(ActorSummaryProjection())

    worker = ProjectionWorker(
        db_pool,
        registry,
        PollOnlyWakeup(),
        poll_interval_seconds=10.0,  # long so we exit via cancel, not timer
    )

    task = asyncio.create_task(worker.run())
    # Yield to let the task start its first iteration and enter
    # wakeup.wait().
    await asyncio.sleep(0.05)
    task.cancel()

    # Either CancelledError or a BaseExceptionGroup containing only
    # CancelledError is acceptable; both indicate clean shutdown.
    try:
        await task
        pytest.fail("Expected CancelledError or ExceptionGroup")
    except asyncio.CancelledError:
        pass
    except BaseExceptionGroup as eg:
        # Every sub-exception must be CancelledError; anything else
        # is a worker bug.
        for sub in eg.exceptions:
            assert isinstance(sub, asyncio.CancelledError), (
                f"Unexpected non-cancellation exception: {sub!r}"
            )
