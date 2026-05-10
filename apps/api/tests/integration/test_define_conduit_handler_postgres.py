"""End-to-end integration test: define_conduit handler against real Postgres.

Mirrors `test_define_zone_handler_postgres.py`. Proves the bare
handler composes with PostgresEventStore: the serialized payload
(including the two endpoint zone IDs) survives jsonb round-trip and
the event lands under stream_type='Conduit' with the right shape.

Stream-type isolation note: the events table's UNIQUE
`(stream_type, stream_id, version)` makes Conduit and Zone streams
independent even when they share a UUID by accident. Coverage of
that invariant lives in `test_postgres_event_store.py:
test_streams_are_isolated_by_type_and_id`.
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
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000c0c0de1")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0c0ee1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SOURCE_ZONE = UUID("01900000-0000-7000-8000-00000000aaaa")
_TARGET_ZONE = UUID("01900000-0000-7000-8000-00000000bbbb")


@pytest.mark.integration
async def test_handler_persists_conduit_defined_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )
    handler = define_conduit.bind(deps)

    conduit_id = await handler(
        DefineConduit(
            name="Detector-to-Storage",
            source_zone_id=_SOURCE_ZONE,
            target_zone_id=_TARGET_ZONE,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert conduit_id == _NEW_ID

    events, version = await deps.event_store.load("Conduit", _NEW_ID)
    assert version == 1
    assert len(events) == 1

    stored = events[0]
    assert stored.event_type == "ConduitDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "conduit_id": str(_NEW_ID),
        "name": "Detector-to-Storage",
        "source_zone_id": str(_SOURCE_ZONE),
        "target_zone_id": str(_TARGET_ZONE),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineConduit"}
    assert stored.occurred_at == _NOW
    assert stored.position > 0
