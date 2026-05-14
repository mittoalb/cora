"""End-to-end integration test: define_zone handler against real Postgres.

Mirrors `test_register_actor_handler_postgres.py` for the Trust BC's
first slice. Proves the bare handler composes with PostgresEventStore:
the serialized payload survives jsonb round-trip and the event lands
under stream_type='Zone' with the right shape.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.trust.features import define_zone
from cora.trust.features.define_zone import DefineZone
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000c0de")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d0de")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_handler_persists_zone_defined_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    handler = define_zone.bind(deps)

    zone_id = await handler(
        DefineZone(name="Detector"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert zone_id == _NEW_ID

    events, version = await deps.event_store.load("Zone", _NEW_ID)
    assert version == 1
    assert len(events) == 1

    stored = events[0]
    assert stored.event_type == "ZoneDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "zone_id": str(_NEW_ID),
        "name": "Detector",
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineZone"}
    assert stored.occurred_at == _NOW
    assert stored.position > 0
