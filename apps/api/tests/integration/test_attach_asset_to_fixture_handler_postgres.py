"""End-to-end integration test: attach_asset_to_fixture handler against Postgres.

Verifies the single-stream-write to the Asset stream + the Fixture
stream stays untouched + the Asset's fixture_id back-reference is
set in the fold of the Asset's events post-attach.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import AssetLevel, load_asset
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.features import (
    add_asset_family,
    attach_asset_to_fixture,
    define_assembly,
    define_family,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC)
_FAMILY_ID = UUID("01900000-0000-7000-8000-00000054cb01")
_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb0e")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000054cb02")
_ASSET_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb0f")
_ADD_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb10")
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054cb03")
_ASSEMBLY_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb1e")
_FIXTURE_ID = UUID("01900000-0000-7000-8000-00000054cb04")
_FIXTURE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb2e")
_ATTACH_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb3e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000dd")
_PARENT_ID = UUID("01900000-0000-7000-8000-000000000fff")


@pytest.mark.integration
async def test_attach_asset_to_fixture_sets_back_reference_in_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _FAMILY_ID,
            _FAMILY_EVENT_ID,
            _ASSET_ID,
            _ASSET_EVENT_ID,
            _ADD_FAMILY_EVENT_ID,
            _ASSEMBLY_ID,
            _ASSEMBLY_DEFINED_EVENT_ID,
            _FIXTURE_ID,
            _FIXTURE_EVENT_ID,
            _ATTACH_EVENT_ID,
        ],
    )

    family_id = await define_family.bind(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="Cam-1", level=AssetLevel.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(
            name="MCTOptics",
            presents_as_family_id=family_id,
            required_slots=frozenset(
                {
                    TemplateSlot(
                        slot_name=SlotName("camera"),
                        required_family_ids=frozenset({family_id}),
                        cardinality=SlotCardinality.EXACTLY_1,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    fixture_id = await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await attach_asset_to_fixture.bind(deps)(
        AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Asset stream now has Registered + AddFamily + AttachedToFixture.
    asset_events, asset_version = await deps.event_store.load("Asset", asset_id)
    assert asset_version == 3
    attach_event = asset_events[2]
    assert attach_event.event_type == "AssetAttachedToFixture"
    assert attach_event.event_id == _ATTACH_EVENT_ID
    assert attach_event.payload == {
        "asset_id": str(asset_id),
        "fixture_id": str(fixture_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert attach_event.correlation_id == _CORRELATION_ID
    assert attach_event.metadata == {"command": "AttachAssetToFixture"}

    # Folded Asset state carries the fixture_id back-reference.
    asset = await load_asset(deps.event_store, asset_id)
    assert asset is not None
    assert asset.fixture_id == fixture_id

    # Fixture stream stays at version 1 (untouched by attach).
    _, fixture_version = await deps.event_store.load("Fixture", fixture_id)
    assert fixture_version == 1
