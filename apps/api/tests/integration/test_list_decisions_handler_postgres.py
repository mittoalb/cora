"""End-to-end: `list_decisions` handler against real Postgres
projection table. Most-important goal: prove the
`confidence_band()` enum's `.value` strings round-trip through the
migration's CHECK constraint on `proj_decision_summary.confidence_band`
(`('Low', 'Medium', 'High', 'Certain')`). With band denormalization
happening at INSERT inside the projection, a typo in the
`ConfidenceBand` enum or a divergent CHECK clause would silently
break in production but the unit test (mock-based) couldn't catch it.

Also exercises:
  - The `confidence_band` column being `NULL` when `confidence` is
    omitted from the command (preserves the not-set distinction).
  - The `confidence_band` filter narrowing results, proving the
    partial-index added in migration 20260513030000 is reachable.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access._projections import register_access_projections
from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.decision._projections import register_decision_projections
from cora.decision.features.list_decisions import ListDecisions
from cora.decision.features.list_decisions import bind as bind_list
from cora.decision.features.register_decision import RegisterDecision
from cora.decision.features.register_decision import bind as bind_register
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.infrastructure.projection import ProjectionRegistry, drain_projections

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
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


async def _drain(db_pool: asyncpg.Pool) -> None:
    """Drain Access + Decision projections (Decision needs Actor
    upstream for cross-aggregate validation, but list_decisions only
    reads proj_decision_summary)."""
    registry = ProjectionRegistry()
    register_access_projections(registry)
    register_decision_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_actor(deps: Kernel) -> UUID:
    """Register an Actor so register_decision's cross-aggregate
    existence check passes. Consumes 2 ids from FixedIdGenerator."""
    return await bind_register_actor(deps)(
        RegisterActor(name="Decider"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_every_band_value_writes_a_check_constraint_accepted_string(
    db_pool: asyncpg.Pool,
) -> None:
    """The load-bearing test: prove the `ConfidenceBand` enum's
    `.value` strings (Low / Medium / High / Certain) all round-trip
    through the `proj_decision_summary.confidence_band` CHECK
    constraint. Without this round-trip, a typo in either the enum
    or the migration would silently break in production but pass
    the projection's mock-based unit test.

    Drives 4 separate Decisions through 4 confidence floats spanning
    each band's interior, plus a 5th with `confidence=None` to prove
    the NULL path survives the CHECK.
    """
    actor_id_holder: list[UUID] = []
    decision_ids: dict[str, UUID] = {}

    bands_under_test = (
        ("low", 0.10),
        ("medium", 0.50),
        ("high", 0.85),
        ("certain", 0.99),
    )
    expected_bands = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "certain": "Certain",
    }

    actor_id = uuid4()
    actor_event_id = uuid4()
    deps_actor = _build_deps(db_pool, [actor_id, actor_event_id])
    actor_id_holder.append(await _seed_actor(deps_actor))

    for label, confidence in bands_under_test:
        decision_id = uuid4()
        event_id = uuid4()
        deps = _build_deps(db_pool, [decision_id, event_id])
        decision_ids[label] = await bind_register(deps)(
            RegisterDecision(
                actor_id=actor_id_holder[0],
                context="RecipeApproval",
                choice=f"approve-{label}",
                confidence=confidence,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Fifth Decision with confidence=None to prove the NULL branch
    # of the CHECK survives end-to-end.
    none_id = uuid4()
    none_event = uuid4()
    deps_none = _build_deps(db_pool, [none_id, none_event])
    decision_ids["none"] = await bind_register(deps_none)(
        RegisterDecision(
            actor_id=actor_id_holder[0],
            context="RecipeApproval",
            choice="approve-no-confidence",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT decision_id, confidence, confidence_band "
            "FROM proj_decision_summary WHERE decision_id = ANY($1)",
            list(decision_ids.values()),
        )
    by_id = {row["decision_id"]: row for row in rows}

    for label, expected_band in expected_bands.items():
        row = by_id[decision_ids[label]]
        assert row["confidence_band"] == expected_band, (
            f"band mismatch for {label}: got {row['confidence_band']!r}, expected {expected_band!r}"
        )

    none_row = by_id[decision_ids["none"]]
    assert none_row["confidence"] is None
    assert none_row["confidence_band"] is None


@pytest.mark.integration
async def test_confidence_band_filter_narrows_results(
    db_pool: asyncpg.Pool,
) -> None:
    """Filter by confidence_band returns only matching rows.

    Exercises the partial-index added in migration
    20260513030000_add_decision_summary_band_idx.sql; without that
    index the query still works but full-scans. This test pins the
    handler's filter SQL behavior, not the planner's choice."""
    actor_id = uuid4()
    deps_actor = _build_deps(db_pool, [actor_id, uuid4()])
    actor_real_id = await _seed_actor(deps_actor)

    high_id = uuid4()
    deps_high = _build_deps(db_pool, [high_id, uuid4()])
    await bind_register(deps_high)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RecipeApproval",
            choice="approve",
            confidence=0.80,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    low_id = uuid4()
    deps_low = _build_deps(db_pool, [low_id, uuid4()])
    await bind_register(deps_low)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RecipeApproval",
            choice="reject",
            confidence=0.10,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    handler = bind_list(deps_high)
    high_page = await handler(
        ListDecisions(confidence_band="High", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(high_page.items) == 1
    assert high_page.items[0].decision_id == high_id
    assert high_page.items[0].confidence_band == "High"

    low_page = await handler(
        ListDecisions(confidence_band="Low", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(low_page.items) == 1
    assert low_page.items[0].decision_id == low_id
    assert low_page.items[0].confidence_band == "Low"


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListDecisions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
