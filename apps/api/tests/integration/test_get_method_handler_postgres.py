"""Integration test: get_method handler against real Postgres."""

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
from cora.recipe.aggregates.method import MethodName, MethodStatus
from cora.recipe.features import define_method, get_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.get_method import GetMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_method_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = UUID("01900000-0000-7000-8000-00000056ef01")
    event_id = UUID("01900000-0000-7000-8000-00000056ef0e")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")

    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([method_id, event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await define_method.bind(deps)(
        DefineMethod(
            name="XRF Fly Mapping",
            needs_capabilities=frozenset({cap1, cap2}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    method = await get_method.bind(deps)(
        GetMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert method is not None
    assert method.id == method_id
    assert method.name == MethodName("XRF Fly Mapping")
    assert method.needs_capabilities == frozenset({cap1, cap2})
    assert method.status is MethodStatus.DEFINED
