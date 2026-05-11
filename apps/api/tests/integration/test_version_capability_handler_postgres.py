"""End-to-end integration test: version_capability against real Postgres.

Round-trip: define + version + load_capability returns the
versioned state with version set.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.capability import (
    CapabilityName,
    CapabilityStatus,
    load_capability,
)
from cora.equipment.features import define_capability, version_capability
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.version_capability import VersionCapability
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
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_version_capability_persists_event_and_round_trips_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    capability_id = UUID("01900000-0000-7000-8000-00000057fa01")
    defined_event_id = UUID("01900000-0000-7000-8000-00000057fa0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-00000057fa0f")

    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([capability_id, defined_event_id, versioned_event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await define_capability.bind(deps)(
        DefineCapability(name="X-ray Fluorescence Mapping"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_capability.bind(deps)(
        VersionCapability(capability_id=capability_id, version_tag="2026-Q3"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Capability", capability_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilityVersioned",
    ]
    versioned = events[1]
    assert versioned.event_id == versioned_event_id
    assert versioned.metadata == {"command": "VersionCapability"}
    assert versioned.payload["version_tag"] == "2026-Q3"

    state = await load_capability(deps.event_store, capability_id)
    assert state is not None
    assert state.name == CapabilityName("X-ray Fluorescence Mapping")
    assert state.status is CapabilityStatus.VERSIONED
    assert state.version == "2026-Q3"
