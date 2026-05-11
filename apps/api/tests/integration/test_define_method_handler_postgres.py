"""End-to-end integration test: define_method handler against real Postgres.

Pinned: needs_capabilities round-trips through jsonb as a sorted
list of UUID strings. The frozenset[UUID] domain shape converts
to list[UUID] at the events layer (see PolicyDefined precedent in
Trust 3c).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_method_persists_event_to_postgres_with_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = UUID("01900000-0000-7000-8000-00000056ed01")
    event_id = UUID("01900000-0000-7000-8000-00000056ed0e")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")

    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([method_id, event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    returned_id = await define_method.bind(deps)(
        DefineMethod(
            name="XRF Fly Mapping",
            needs_capabilities=frozenset({cap2, cap1}),  # unsorted input
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == method_id

    events, version = await deps.event_store.load("Method", method_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "MethodDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "method_id": str(method_id),
        "name": "XRF Fly Mapping",
        # Sorted by UUID string form (deterministic).
        "needs_capabilities": sorted([str(cap1), str(cap2)]),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == event_id
    assert stored.metadata == {"command": "DefineMethod"}
    assert stored.occurred_at == _NOW


@pytest.mark.integration
async def test_define_method_persists_procedural_method_with_empty_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    """Procedural Method (no equipment requirement) round-trips
    through jsonb with `needs_capabilities = []`."""
    method_id = UUID("01900000-0000-7000-8000-00000056ee01")
    event_id = UUID("01900000-0000-7000-8000-00000056ee0e")

    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([method_id, event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await define_method.bind(deps)(
        DefineMethod(name="Sample Cleaning", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Method", method_id)
    assert events[0].payload["needs_capabilities"] == []
