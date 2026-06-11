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

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000c0c0de1")
_TRAVERSALS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-00000c0c0de2")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0c0ee1")
_LOGBOOK_OPENED_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0c0ee2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SOURCE_ZONE = UUID("01900000-0000-7000-8000-00000000aaaa")
_TARGET_ZONE = UUID("01900000-0000-7000-8000-00000000bbbb")


@pytest.mark.integration
async def test_handler_persists_conduit_defined_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _NEW_ID,
            _TRAVERSALS_LOGBOOK_ID,
            _DEFINED_EVENT_ID,
            _LOGBOOK_OPENED_EVENT_ID,
        ],
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

    # in one transactional append.
    assert version == 2
    assert [e.event_type for e in events] == ["ConduitDefined", "ConduitLogbookOpened"]

    defined = events[0]
    assert defined.schema_version == 1
    assert defined.payload == {
        "conduit_id": str(_NEW_ID),
        "name": "Detector-to-Storage",
        "source_zone_id": str(_SOURCE_ZONE),
        "target_zone_id": str(_TARGET_ZONE),
        "occurred_at": _NOW.isoformat(),
    }
    assert defined.correlation_id == _CORRELATION_ID
    assert defined.causation_id is None
    assert defined.event_id == _DEFINED_EVENT_ID
    assert defined.metadata == {"command": "DefineConduit"}
    assert defined.occurred_at == _NOW
    assert defined.position > 0

    logbook_opened = events[1]
    assert logbook_opened.event_id == _LOGBOOK_OPENED_EVENT_ID
    assert logbook_opened.payload["conduit_id"] == str(_NEW_ID)
    assert logbook_opened.payload["logbook_id"] == str(_TRAVERSALS_LOGBOOK_ID)
    assert logbook_opened.payload["kind"] == "verdict"
    # Schema is captured in the payload (audit trail of column shape
    # at the moment of channel-open). Round-trips through jsonb.
    assert set(logbook_opened.payload["schema"]["fields"]) == {
        "actor_id",
        "command_name",
        "decision",
        "reason",
    }
