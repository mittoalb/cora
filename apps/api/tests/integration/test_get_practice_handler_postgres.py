"""Integration test: get_practice handler against real Postgres."""

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
from cora.recipe.aggregates.practice import PracticeName, PracticeStatus
from cora.recipe.features import define_practice, get_practice
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.get_practice import GetPractice

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_practice_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    practice_id = UUID("01900000-0000-7000-8000-00000059ee01")
    event_id = UUID("01900000-0000-7000-8000-00000059ee0e")
    method_id = UUID("01900000-0000-7000-8000-000000000333")
    site_id = UUID("01900000-0000-7000-8000-000000000444")

    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([practice_id, event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await define_practice.bind(deps)(
        DefinePractice(
            name="APS Standard Tomography",
            method_id=method_id,
            site_id=site_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    practice = await get_practice.bind(deps)(
        GetPractice(practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert practice is not None
    assert practice.id == practice_id
    assert practice.name == PracticeName("APS Standard Tomography")
    assert practice.method_id == method_id
    assert practice.site_id == site_id
    assert practice.status is PracticeStatus.DEFINED
    assert practice.current_version is None
