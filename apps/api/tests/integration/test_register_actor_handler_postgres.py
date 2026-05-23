"""End-to-end integration test: register_actor handler against real Postgres.

Unit tests cover the handler against InMemoryEventStore. PostgresEventStore
integration tests cover the adapter in isolation. This test proves the
two compose: the serialized payload survives jsonb round-trip and the
event lands with the right shape.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access.features import register_actor
from cora.access.features.register_actor import RegisterActor
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000beef")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000eeef")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_handler_persists_actor_registered_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    profile_store = make_pg_profile_store(db_pool)
    handler = register_actor.bind(deps, profile_store=profile_store)

    actor_id = await handler(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert actor_id == _NEW_ID

    events, version = await deps.event_store.load("Actor", _NEW_ID)
    assert version == 1
    assert len(events) == 1

    stored = events[0]
    # PII vault: V2 discriminator + payload carries no `name`.
    assert stored.event_type == "ActorRegisteredV2"
    assert stored.schema_version == 1
    assert stored.payload == {
        "actor_id": str(_NEW_ID),
        "occurred_at": _NOW.isoformat(),
        "kind": "human",
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterActor"}
    assert stored.occurred_at == _NOW
    assert stored.position > 0

    # Display name landed in the actor_profile vault.
    profile = await profile_store.get(_NEW_ID)
    assert profile is not None
    assert profile.name == "Doga"
    assert profile.created_at == _NOW
