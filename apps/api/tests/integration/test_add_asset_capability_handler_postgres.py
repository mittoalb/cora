"""End-to-end integration test: add_asset_capability against real Postgres.

Pin: payload round-trips through jsonb with capability_id as a UUID
string; the evolver reconstructs into the frozenset on next load.
Two scenarios — adding a single capability, then verifying that
load+fold returns a state with the capability in the set.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel, load_asset
from cora.equipment.features import add_asset_capability, register_asset
from cora.equipment.features.add_asset_capability import AddAssetCapability
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000056fa00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_add_asset_capability_persists_event_and_round_trips_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000056fa01")
    register_event_id = UUID("01900000-0000-7000-8000-00000056fa0e")
    add_event_id = UUID("01900000-0000-7000-8000-00000056fa0f")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")

    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([asset_id, register_event_id, add_event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetCapabilityAdded",
    ]
    added = events[1]
    assert added.event_id == add_event_id
    assert added.metadata == {"command": "AddAssetCapability"}
    assert added.payload["capability_id"] == str(cap1)

    # Fold-on-read reconstructs the capabilities frozenset.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.capabilities == frozenset({cap1})
