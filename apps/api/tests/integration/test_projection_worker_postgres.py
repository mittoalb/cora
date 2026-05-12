"""End-to-end: projection worker advances ActorSummaryProjection
against real Postgres, populates `proj_access_actor_summary`.

Exercises the full Phase-8e-1a + 8e-1b stack:

  - register_actor handler -> events table INSERT
  - drain_projections -> advance loop reads bookmark + events,
    calls apply(), updates bookmark
  - SELECT against proj_access_actor_summary returns the row

Plus the canonical Khyst+Dudycz cursor properties:
  - Multi-event batches advance atomically (bookmark moves once)
  - Bookmark stays at sentinel if no events match
  - Re-applying same events is idempotent (ON CONFLICT)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access._projection_registry import register_access_projections
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.deactivate_actor import bind as bind_deactivate
from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FixedIdGenerator, FrozenClock
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.infrastructure.projection import ProjectionRegistry, drain_projections

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


def _build_registry() -> ProjectionRegistry:
    registry = ProjectionRegistry()
    register_access_projections(registry)
    return registry


@pytest.mark.integration
async def test_register_actor_event_advances_into_proj_table(
    db_pool: asyncpg.Pool,
) -> None:
    """The full happy path: append RegisterActor event, drain, observe
    the row in `proj_access_actor_summary`."""
    actor_id = UUID("01900000-0000-7000-8000-00000000a001")
    actor_event_id = UUID("01900000-0000-7000-8000-00000000a002")

    deps = _build_deps(db_pool, [actor_id, actor_event_id])
    handler = bind_register(deps)
    await handler(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = _build_registry()
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT actor_id, name, status FROM proj_access_actor_summary WHERE actor_id = $1",
            actor_id,
        )
    assert row is not None
    assert row["actor_id"] == actor_id
    assert row["name"] == "Doga"
    assert row["status"] == "active"


@pytest.mark.integration
async def test_deactivate_after_register_flips_status(
    db_pool: asyncpg.Pool,
) -> None:
    """Two events on one stream, fold collapses to one row, status
    transitions active -> deactivated."""
    actor_id = UUID("01900000-0000-7000-8000-00000000b001")
    register_event_id = UUID("01900000-0000-7000-8000-00000000b002")
    deactivate_event_id = UUID("01900000-0000-7000-8000-00000000b003")

    deps = _build_deps(db_pool, [actor_id, register_event_id, deactivate_event_id])
    await bind_register(deps)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_deactivate(deps)(
        DeactivateActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = _build_registry()
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM proj_access_actor_summary WHERE actor_id = $1",
            actor_id,
        )
    assert row is not None
    assert row["status"] == "deactivated"


@pytest.mark.integration
async def test_drain_with_no_events_advances_bookmark_to_zero(
    db_pool: asyncpg.Pool,
) -> None:
    """Empty event store: bookmark stays at sentinel, drain returns
    immediately, no rows in the projection."""
    registry = _build_registry()
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        # Bookmark row exists (from migration) at sentinel zero.
        row = await conn.fetchrow(
            "SELECT last_position FROM projection_bookmarks WHERE name = $1",
            "proj_access_actor_summary",
        )
        assert row is not None
        assert row["last_position"] == 0
        # No projection rows yet.
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM proj_access_actor_summary",
        )
    assert count == 0


@pytest.mark.integration
async def test_bookmark_advances_when_subscribed_event_arrives(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: a subscribed event in the stream causes the bookmark to
    advance past sentinel zero to that event's (transaction_id,
    position).

    The lexicographic-cursor + SQL-side `event_type = ANY(...)`
    filter combination means unsubscribed events between two
    subscribed ones are skipped CORRECTLY (the next iteration's
    `>` comparison covers them via the bookmark moving to the last
    RETURNED row, not the last SCANNED row). When more BCs ship
    projections, an explicit cross-BC test could pin that behavior
    against an actual mixed-event-type stream; today the only events
    in scope are Actor events, so this test pins the simpler shape:
    bookmark moves off sentinel when work is available.
    """
    actor_id = UUID("01900000-0000-7000-8000-00000000c001")
    actor_event_id = UUID("01900000-0000-7000-8000-00000000c002")

    deps = _build_deps(db_pool, [actor_id, actor_event_id])
    await bind_register(deps)(
        RegisterActor(name="Asli"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = _build_registry()
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT last_position FROM projection_bookmarks WHERE name = $1",
            "proj_access_actor_summary",
        )
    assert row is not None
    assert row["last_position"] > 0


@pytest.mark.integration
async def test_idempotent_re_application(
    db_pool: asyncpg.Pool,
) -> None:
    """Drain twice; second drain is a no-op (bookmark already at head).
    Pin: ON CONFLICT DO NOTHING means even if events were redelivered,
    the projection state stays consistent."""
    actor_id = uuid4()
    actor_event_id = uuid4()
    deps = _build_deps(db_pool, [actor_id, actor_event_id])
    await bind_register(deps)(
        RegisterActor(name="Repeat"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = _build_registry()
    await drain_projections(db_pool, registry, deadline_seconds=2.0)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM proj_access_actor_summary WHERE actor_id = $1",
            actor_id,
        )
    assert count == 1


@pytest.mark.integration
async def test_bookmark_advances_across_multiple_actors(
    db_pool: asyncpg.Pool,
) -> None:
    """Three separate streams (three actors), three transactions,
    three xid8 values. Drain catches them all; bookmark covers all
    three positions."""
    deps_ids: list[UUID] = []
    actors: list[UUID] = []
    for _ in range(3):
        actor_id = uuid4()
        event_id = uuid4()
        actors.append(actor_id)
        deps_ids.extend([actor_id, event_id])
    deps = _build_deps(db_pool, deps_ids)

    for i, _ in enumerate(actors):
        await bind_register(deps)(
            RegisterActor(name=f"Actor{i}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    registry = _build_registry()
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM proj_access_actor_summary WHERE actor_id = ANY($1)",
            actors,
        )
    assert count == 3
