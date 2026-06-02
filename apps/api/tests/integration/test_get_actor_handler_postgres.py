"""Integration test: get_actor handler against real Postgres.

PII vault: the handler returns ActorView (aggregate state + display
name resolved from `actor_profile`). The post-register read pulls
the trimmed name from the vault row written by the same handler's
two-step write path.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access.features import get_actor, register_actor
from cora.access.features.get_actor import GetActor
from cora.access.features.register_actor import RegisterActor
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000c0de")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ee0d")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_actor_loads_view_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_ACTOR_ID, _REGISTER_EVENT_ID])
    profile_store = make_pg_profile_store(db_pool)

    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    view = await get_actor.bind(deps, profile_store=profile_store)(
        GetActor(actor_id=_ACTOR_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.actor.id == _ACTOR_ID
    assert view.actor.active is True
    assert view.display_name == "Doga"
