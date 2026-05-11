"""End-to-end integration test: define_practice handler against real Postgres.

Pinned: method_id and site_id round-trip through jsonb as UUID
strings; the evolver reconstructs both from payload primitives.
Eventual-consistency stance — neither id is verified against the
corresponding aggregate stream.
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
from cora.recipe.features import define_practice
from cora.recipe.features.define_practice import DefinePractice

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_practice_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    practice_id = UUID("01900000-0000-7000-8000-00000059ed01")
    event_id = UUID("01900000-0000-7000-8000-00000059ed0e")
    method_id = UUID("01900000-0000-7000-8000-000000000111")
    site_id = UUID("01900000-0000-7000-8000-000000000222")

    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([practice_id, event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    returned_id = await define_practice.bind(deps)(
        DefinePractice(
            name="APS Sector 2 XRF Fly Mapping",
            method_id=method_id,
            site_id=site_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == practice_id

    events, version = await deps.event_store.load("Practice", practice_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "PracticeDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "practice_id": str(practice_id),
        "name": "APS Sector 2 XRF Fly Mapping",
        "method_id": str(method_id),
        "site_id": str(site_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.event_id == event_id
    assert stored.metadata == {"command": "DefinePractice"}
