"""End-to-end integration test: register_actor handler against real Postgres.

Unit tests cover the handler against InMemoryEventStore. PostgresEventStore
integration tests cover the adapter in isolation. This test proves the
two compose: the serialized payload survives jsonb round-trip and the
event lands with the right shape.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access.application import make_register_actor_handler
from cora.access.domain import RegisterActor
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000beef")
_INVOKER_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_handler_persists_actor_registered_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
    )
    handler = make_register_actor_handler(deps)

    actor_id = await handler(
        RegisterActor(name="Doga"),
        actor_id=_INVOKER_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert actor_id == _NEW_ID

    events, version = await deps.event_store.load("Actor", _NEW_ID)
    assert version == 1
    assert len(events) == 1

    stored = events[0]
    assert stored.event_type == "ActorRegistered"
    assert stored.schema_version == 1
    assert stored.payload == {
        "actor_id": str(_NEW_ID),
        "name": "Doga",
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.metadata == {"command": "RegisterActor"}
    assert stored.occurred_at == _NOW
    assert stored.position > 0
