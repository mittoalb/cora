"""End-to-end integration test: decommission_asset handler against real Postgres.

Three scenarios cover the multi-source-state guard (Commissioned ->
Decommissioned, Active -> Decommissioned, and Maintenance ->
Decommissioned, the third source widened by the Maintenance state); all three are
exercised against real Postgres so the load+fold+decide+append
cycle is validated for every allowed source state with the real
event store.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features import (
    activate_asset,
    decommission_asset,
    enter_asset_maintenance,
    register_asset,
)
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.enter_asset_maintenance import EnterAssetMaintenance
from cora.equipment.features.register_asset import RegisterAsset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000054ed00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_decommission_asset_persists_event_from_commissioned_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Commissioned -> Decommissioned (skipping activate). Operator-
    changed-mind path."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ed01")
    register_event_id = UUID("01900000-0000-7000-8000-00000054ed0e")
    decommission_event_id = UUID("01900000-0000-7000-8000-00000054ed0f")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, decommission_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetDecommissioned",
    ]
    decommed = events[1]
    assert decommed.event_id == decommission_event_id
    assert decommed.metadata == {"command": "DecommissionAsset"}


@pytest.mark.integration
async def test_decommission_asset_persists_event_from_active_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Full happy path: register + activate + decommission."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ee01")
    register_event_id = UUID("01900000-0000-7000-8000-00000054ee0e")
    activate_event_id = UUID("01900000-0000-7000-8000-00000054ee0f")
    decommission_event_id = UUID("01900000-0000-7000-8000-00000054ee10")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, activate_event_id, decommission_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-32-ID", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetDecommissioned",
    ]
    decommed = events[2]
    assert decommed.event_id == decommission_event_id


@pytest.mark.integration
async def test_decommission_asset_persists_event_from_maintenance_state(
    db_pool: asyncpg.Pool,
) -> None:
    """5e widening: decommission accepts Maintenance as third source.
    Full path: register + activate + enter_asset_maintenance + decommission."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ef01")
    register_event_id = UUID("01900000-0000-7000-8000-00000054ef0e")
    activate_event_id = UUID("01900000-0000-7000-8000-00000054ef0f")
    enter_event_id = UUID("01900000-0000-7000-8000-00000054ef10")
    decommission_event_id = UUID("01900000-0000-7000-8000-00000054ef11")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            asset_id,
            register_event_id,
            activate_event_id,
            enter_event_id,
            decommission_event_id,
        ],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-7BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await enter_asset_maintenance.bind(deps)(
        EnterAssetMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetMaintenanceEntered",
        "AssetDecommissioned",
    ]
    decommed = events[3]
    assert decommed.event_id == decommission_event_id
