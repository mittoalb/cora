"""Shared test helpers for integration tests against real Postgres.

Mirrors `tests/unit/_helpers.py::build_deps` but constructs a Kernel
backed by `PostgresEventStore` + `PostgresIdempotencyStore` over the
testcontainers `db_pool` fixture from `tests/integration/conftest.py`.

## Usage

```python
from tests.integration._helpers import build_postgres_deps

deps = build_postgres_deps(db_pool, ids=[method_id, event_id], now=_NOW)
deps = build_postgres_deps(db_pool, ids=[...], now=_NOW, authorize=RecordingAuthorize())
```

## Why a separate factory from the unit helper

Integration tests need PostgresEventStore + PostgresIdempotencyStore
constructed from the per-test `db_pool` fixture; unit tests use the
in-memory adapters with no pool. The two flows can't share a single
factory without either (a) optional pool with conditional adapter
selection (silently surprising) or (b) cross-tier imports (couples
test tiers).

`now` is required (no DEFAULT_NOW analog): integration tests pin a
per-test timestamp so the persisted event's `occurred_at` traces
back to the test that wrote it.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_postgres_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AlwaysCoveredClearanceLookup,
    AlwaysQuietCautionLookup,
    Authorize,
    CautionLookup,
    ClearanceLookup,
    EventStore,
    FixedIdGenerator,
    FrozenClock,
    IdempotencyStore,
    LLMPort,
)


def build_postgres_deps(
    pool: asyncpg.Pool,
    *,
    now: datetime,
    ids: list[UUID] | None = None,
    authorize: Authorize | None = None,
    event_store: EventStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
    clearance_lookup: ClearanceLookup | None = None,
    caution_lookup: CautionLookup | None = None,
    llm: LLMPort | None = None,
) -> Kernel:
    """Build a Kernel for integration-test handler invocation against real Postgres.

    Defaults: AllowAllAuthorize, fresh PostgresEventStore(pool), fresh
    PostgresIdempotencyStore(pool), `AlwaysCoveredClearanceLookup` (the
    safety-gate bypass stub), `AlwaysQuietCautionLookup` (the caution-
    snapshot quiet stub). Pass `event_store=` / `idempotency_store=` /
    `clearance_lookup=` / `caution_lookup=` to share an already-
    constructed adapter or to exercise a specific behavior (e.g.,
    gate tests pass `PostgresClearanceLookup(pool)` and seed a real
    clearance; snapshot tests pass `PostgresCautionLookup(pool)` and
    seed a real caution via `register_caution`).

    `ids=` queues UUIDs for the FixedIdGenerator (handler consumes them
    in order: aggregate ids first, then event ids per emitted event).
    """
    return make_postgres_kernel(
        pool,
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(now),
        id_generator=FixedIdGenerator(list(ids or [])),
        authorize=authorize or AllowAllAuthorize(),
        event_store=event_store,
        idempotency_store=idempotency_store,
        clearance_lookup=clearance_lookup or AlwaysCoveredClearanceLookup(),
        caution_lookup=caution_lookup or AlwaysQuietCautionLookup(),
        llm=llm,
    )


_DEFAULT_SEED_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DEFAULT_SEED_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")


async def seed_capability_pg(
    event_store: EventStore,
    capability_id: UUID,
    *,
    code: str = "cora.capability.test",
    name: str = "TestCapability",
    shapes: object | None = None,
    now: datetime | None = None,
    correlation_id: UUID = _DEFAULT_SEED_CORRELATION_ID,
    principal_id: UUID = _DEFAULT_SEED_PRINCIPAL_ID,
) -> None:
    """Seed a Capability stream against a Postgres event store.

    Phase 6l-strict bulk-migration helper: mirrors `tests.unit._helpers.seed_capability`
    but threads the Postgres event store explicitly. Used by integration
    tests that call `DefineMethod(...)` or `RegisterProcedure(...)` —
    the bound Capability stream must exist before the handler runs
    (eventual-consistency: handler raises `CapabilityNotFoundError`
    when the stream is missing). Defaults to both METHOD + PROCEDURE
    executor shapes so the same seed serves both binding paths.
    """
    import contextlib
    from uuid import uuid4 as _uuid4

    from cora.infrastructure.event_envelope import to_new_event as _to_new_event
    from cora.infrastructure.ports.event_store import ConcurrencyError
    from cora.recipe.aggregates.capability import (
        CapabilityCode,
        CapabilityName,
        ExecutorShape,
        RecipeCapabilityDefined,
    )
    from cora.recipe.aggregates.capability import (
        event_type_name as capability_event_type_name,
    )
    from cora.recipe.aggregates.capability import (
        to_payload as capability_to_payload,
    )

    occurred_at = now or datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
    shapes_set: frozenset[ExecutorShape] = shapes or frozenset(  # type: ignore[assignment]
        {ExecutorShape.METHOD, ExecutorShape.PROCEDURE}
    )
    event = RecipeCapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode(code).value,
        name=CapabilityName(name).value,
        required_affordances=frozenset(),
        executor_shapes=shapes_set,
        occurred_at=occurred_at,
    )
    # Idempotent seed: another test in the same PG db_pool may have
    # already seeded this capability_id; tolerated via contextlib.suppress
    # so test modules sharing a `_CAPABILITY_ID` constant can call
    # seed_capability_pg freely from each test without coordinating.
    with contextlib.suppress(ConcurrencyError):
        await event_store.append(
            stream_type="Capability",
            stream_id=capability_id,
            expected_version=0,
            events=[
                _to_new_event(
                    event_type=capability_event_type_name(event),
                    payload=capability_to_payload(event),
                    occurred_at=occurred_at,
                    event_id=_uuid4(),
                    command_name="DefineCapability",
                    correlation_id=correlation_id,
                    principal_id=principal_id,
                )
            ],
        )


__all__ = ["build_postgres_deps", "seed_capability_pg"]
