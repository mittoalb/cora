"""End-to-end: handler call lands `principal_id` on stored events
.

The arch fitness test
[tests/architecture/test_envelope_principal_id.py] proves every
handler PASSES the kwarg into `to_new_event`. This test proves the
value actually round-trips: caller passes principal_id=X to
register_actor handler -> event store INSERT writes X -> SELECT
reads X back on `events.principal_id`.

Two scenarios:

  - Single-event handler (register_actor): one event, one
    principal_id round-trip.
  - Multi-event handler (define_conduit): two events
    (ConduitDefined + ConduitLogbookOpened),
    same principal_id on both.

If the handler accidentally drops the kwarg (regression that the
arch test missed somehow), the assertion `event.principal_id == X`
fails. If the adapter SQL drops the column (regression of the
9b-a-cleanup worker fix), the read returns None and the assertion
fails.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.infrastructure.kernel import Kernel
from cora.trust.features.define_conduit import DefineConduit
from cora.trust.features.define_conduit import bind as bind_define_conduit
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000bb55")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


@pytest.mark.integration
async def test_register_actor_handler_writes_principal_id_on_event(
    db_pool: asyncpg.Pool,
) -> None:
    """Single-event handler: principal_id ends up on the one event
    the decider emits."""
    actor_id = uuid4()
    event_id = uuid4()
    deps = _build_deps(db_pool, [actor_id, event_id])
    handler = bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))
    await handler(
        RegisterActor(name="Alice"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Actor", actor_id)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "ActorRegisteredV2"
    assert events[0].principal_id == _PRINCIPAL_ID, (
        f"register_actor handler wrote principal_id="
        f"{events[0].principal_id!r}, expected {_PRINCIPAL_ID!r}. "
        f"The handler may not be threading the kwarg into to_new_event."
    )


@pytest.mark.integration
async def test_define_conduit_handler_writes_principal_id_on_all_events(
    db_pool: asyncpg.Pool,
) -> None:
    """Multi-event handler: define_conduit emits BOTH ConduitDefined
    and ConduitLogbookOpened, and both events must
    carry the same principal_id (one handler call -> one principal,
    even when N events fire)."""
    conduit_id = uuid4()
    logbook_id = uuid4()
    event_id_a = uuid4()
    event_id_b = uuid4()
    source_zone = uuid4()
    target_zone = uuid4()
    deps = _build_deps(db_pool, [conduit_id, logbook_id, event_id_a, event_id_b])
    handler = bind_define_conduit(deps)
    await handler(
        DefineConduit(
            name="DetectorToStorage",
            source_zone_id=source_zone,
            target_zone_id=target_zone,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Conduit", conduit_id)
    assert version == 2
    assert len(events) == 2
    assert {e.event_type for e in events} == {
        "ConduitDefined",
        "ConduitLogbookOpened",
    }
    assert all(e.principal_id == _PRINCIPAL_ID for e in events), (
        f"At least one event was missing the principal_id. Got: "
        f"{[(e.event_type, e.principal_id) for e in events]}"
    )
