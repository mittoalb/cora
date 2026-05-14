"""Integration test: get_actor handler against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access.aggregates.actor import ActorName
from cora.access.features import get_actor, register_actor
from cora.access.features.get_actor import GetActor
from cora.access.features.register_actor import RegisterActor
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000c0de")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ee0d")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_actor_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_ACTOR_ID, _REGISTER_EVENT_ID])

    await register_actor.bind(deps)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    actor = await get_actor.bind(deps)(
        GetActor(actor_id=_ACTOR_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert actor is not None
    assert actor.id == _ACTOR_ID
    assert actor.name == ActorName("Doga")
    assert actor.is_active is True
