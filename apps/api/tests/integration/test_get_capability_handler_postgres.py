"""Integration test: get_capability handler against real Postgres."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.capability import CapabilityName, CapabilityStatus
from cora.equipment.features import define_capability, get_capability
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.get_capability import GetCapability
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000054cb01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb0e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_capability_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_CAPABILITY_ID, _EVENT_ID]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await define_capability.bind(deps)(
        DefineCapability(name="X-ray Fluorescence Mapping"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    capability = await get_capability.bind(deps)(
        GetCapability(capability_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert capability is not None
    assert capability.id == _CAPABILITY_ID
    assert capability.name == CapabilityName("X-ray Fluorescence Mapping")
    assert capability.status is CapabilityStatus.DEFINED
