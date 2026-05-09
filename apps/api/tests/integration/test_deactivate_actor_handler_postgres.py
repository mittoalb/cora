"""End-to-end integration test: deactivate_actor handler against real Postgres.

Proves the load+fold+decide+append flow composes against the real
PostgresEventStore: serialized payload survives jsonb round-trip,
from_stored deserializes correctly, the second event lands at version 2.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access.features import deactivate_actor, register_actor
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000cafe")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_handler_deactivates_actor_against_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_ACTOR_ID]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
    )

    # First register, then deactivate.
    await register_actor.bind(deps)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deactivate_actor.bind(deps)(
        DeactivateActor(actor_id=_ACTOR_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Actor", _ACTOR_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["ActorRegistered", "ActorDeactivated"]
    assert events[1].payload == {
        "actor_id": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert events[1].metadata == {"command": "DeactivateActor"}
    assert events[1].correlation_id == _CORRELATION_ID
