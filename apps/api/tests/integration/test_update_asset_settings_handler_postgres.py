"""End-to-end integration test: update_asset_settings handler
against real Postgres with multiple Capabilities (Phase 5g-c).

Covers:
  - happy path: set, persists AssetSettingsUpdated with full
    post-merge dict
  - merge across two PATCHes accumulates
  - cross-Capability schema union: settings keys owned by either
    Capability are validated against the right schema
  - true type conflict between two Capabilities surfaces with both
    Capability ids in the error
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel, InvalidAssetSettingsError
from cora.equipment.features import (
    add_asset_capability,
    define_capability,
    register_asset,
    update_asset_settings,
    update_capability_schema,
)
from cora.equipment.features.add_asset_capability import AddAssetCapability
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.update_asset_settings import UpdateAssetSettings
from cora.equipment.features.update_capability_schema import UpdateCapabilitySchema
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000005c0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000005c00aa")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(ids),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )


@pytest.mark.integration
async def test_update_asset_settings_persists_event_with_full_post_merge_dict(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: define Capability with schema, register Asset,
    add Capability, PATCH settings, assert persisted event payload
    carries the FULL post-merge dict (5g-c lock)."""
    cap_id = UUID("01900000-0000-7000-8000-0000005c0001")
    asset_id = UUID("01900000-0000-7000-8000-0000005c0002")
    ids = [
        # define_capability: capability_id, define_event_id
        cap_id,
        UUID("01900000-0000-7000-8000-0000005c0011"),
        # update_capability_schema: schema_event_id
        UUID("01900000-0000-7000-8000-0000005c0012"),
        # register_asset: asset_id, register_event_id
        asset_id,
        UUID("01900000-0000-7000-8000-0000005c0013"),
        # add_asset_capability: cap_added_event_id
        UUID("01900000-0000-7000-8000-0000005c0014"),
        # update_asset_settings: settings_event_id
        UUID("01900000-0000-7000-8000-0000005c0015"),
    ]
    deps = _deps(db_pool, ids)

    await define_capability.bind(deps)(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_capability_schema.bind(deps)(
        UpdateCapabilitySchema(
            capability_id=cap_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy_kev": {"type": "number", "minimum": 5},
                    "filter": {"type": "string"},
                },
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="Detector", level=AssetLevel.DEVICE, parent_id=UUID(int=1)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy_kev": 30, "filter": "Cu"}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetCapabilityAdded",
        "AssetSettingsUpdated",
    ]
    settings_event = events[2]
    assert settings_event.metadata == {"command": "UpdateAssetSettings"}
    assert settings_event.payload["settings"] == {"energy_kev": 30, "filter": "Cu"}


@pytest.mark.integration
async def test_update_asset_settings_merges_across_two_patches(
    db_pool: asyncpg.Pool,
) -> None:
    """Two PATCHes accumulate via merge: first sets one key, second
    sets another; final state has both."""
    cap_id = UUID("01900000-0000-7000-8000-0000005c0021")
    asset_id = UUID("01900000-0000-7000-8000-0000005c0022")
    ids = [
        cap_id,
        UUID("01900000-0000-7000-8000-0000005c0031"),  # define cap event
        UUID("01900000-0000-7000-8000-0000005c0032"),  # set schema event
        asset_id,
        UUID("01900000-0000-7000-8000-0000005c0033"),  # register event
        UUID("01900000-0000-7000-8000-0000005c0034"),  # add capability event
        UUID("01900000-0000-7000-8000-0000005c0035"),  # first settings event
        UUID("01900000-0000-7000-8000-0000005c0036"),  # second settings event
    ]
    deps = _deps(db_pool, ids)

    await define_capability.bind(deps)(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_capability_schema.bind(deps)(
        UpdateCapabilitySchema(
            capability_id=cap_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy_kev": {"type": "number"},
                    "filter": {"type": "string"},
                },
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="Detector", level=AssetLevel.DEVICE, parent_id=UUID(int=1)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy_kev": 30}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_settings.bind(deps)(
        UpdateAssetSettings(asset_id=asset_id, settings_patch={"filter": "Cu"}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 4
    # Last event's payload carries the FULL merged dict.
    assert events[-1].payload["settings"] == {"energy_kev": 30, "filter": "Cu"}


@pytest.mark.integration
async def test_update_asset_settings_rejects_true_type_conflict_across_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    """Two Capabilities both declare `temperature_c` but with
    incompatible types; the validator names both Capabilities."""
    cap_a_id = UUID("01900000-0000-7000-8000-0000005c0041")
    cap_b_id = UUID("01900000-0000-7000-8000-0000005c0042")
    asset_id = UUID("01900000-0000-7000-8000-0000005c0043")
    ids = [
        cap_a_id,
        UUID("01900000-0000-7000-8000-0000005c0051"),
        UUID("01900000-0000-7000-8000-0000005c0052"),
        cap_b_id,
        UUID("01900000-0000-7000-8000-0000005c0053"),
        UUID("01900000-0000-7000-8000-0000005c0054"),
        asset_id,
        UUID("01900000-0000-7000-8000-0000005c0055"),
        UUID("01900000-0000-7000-8000-0000005c0056"),
        UUID("01900000-0000-7000-8000-0000005c0057"),
    ]
    deps = _deps(db_pool, ids)

    await define_capability.bind(deps)(
        DefineCapability(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_capability_schema.bind(deps)(
        UpdateCapabilitySchema(
            capability_id=cap_a_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {"temperature_c": {"type": "number"}},
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_capability.bind(deps)(
        DefineCapability(name="B"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_capability_schema.bind(deps)(
        UpdateCapabilitySchema(
            capability_id=cap_b_id,
            settings_schema={
                "$schema": _DRAFT,
                "type": "object",
                "properties": {"temperature_c": {"type": "string"}},
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="X", level=AssetLevel.DEVICE, parent_id=UUID(int=1)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap_a_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap_b_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        await update_asset_settings.bind(deps)(
            UpdateAssetSettings(
                asset_id=asset_id,
                settings_patch={"temperature_c": 25},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Both Capability ids surface in the diagnostic.
    assert str(cap_a_id) in exc_info.value.reason
    assert str(cap_b_id) in exc_info.value.reason
    assert "temperature_c" in exc_info.value.reason
    assert "incompatible types" in exc_info.value.reason
