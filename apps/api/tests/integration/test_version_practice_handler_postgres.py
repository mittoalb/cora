"""End-to-end integration test: version_practice against real Postgres."""

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
from cora.recipe.aggregates.practice import PracticeStatus, load_practice
from cora.recipe.features import define_practice, version_practice
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.version_practice import VersionPractice

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_version_practice_persists_event_and_round_trips_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    practice_id = UUID("01900000-0000-7000-8000-0000005afa01")
    defined_event_id = UUID("01900000-0000-7000-8000-0000005afa0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-0000005afa0f")
    method_id = UUID("01900000-0000-7000-8000-000000000111")
    site_id = UUID("01900000-0000-7000-8000-000000000222")

    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([practice_id, defined_event_id, versioned_event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await define_practice.bind(deps)(
        DefinePractice(name="X", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_practice.bind(deps)(
        VersionPractice(practice_id=practice_id, version_tag="2026-Q3"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Practice", practice_id)
    assert version == 2
    assert [e.event_type for e in events] == ["PracticeDefined", "PracticeVersioned"]
    versioned = events[1]
    assert versioned.event_id == versioned_event_id
    assert versioned.payload["version_tag"] == "2026-Q3"

    state = await load_practice(deps.event_store, practice_id)
    assert state is not None
    assert state.status is PracticeStatus.VERSIONED
    assert state.current_version == "2026-Q3"
    assert state.method_id == method_id
    assert state.site_id == site_id
