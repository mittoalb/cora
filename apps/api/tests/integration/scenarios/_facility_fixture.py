"""Shared facility-hierarchy install helper for 2-BM-shape scenario tests.

Extracted when the 3rd scenario re-registered Argonne + APS + 2-BM Unit
by hand (per [[project_scenario_taxonomy]] watch item). The install scenario
(`test_aps_facility_*`) is NOT a caller: it IS the source-of-truth
install ceremony being tested, with its own facility-level extras (Agent,
Practice, Clearance, Supply, Caution).

## Two coupled functions

`install_aps_unit()` executes the ceremony; `facility_id_prefix()`
returns the matching `FixedIdGenerator` queue prefix. Callers must use
both together: the prefix MUST sit at the head of `_id_queue()` and the
install call MUST happen before any scenario-specific commands consume
the queue. Drift between the two corrupts every downstream id allocation.

## Why scenario-supplied UUIDs (not canonical)

Each scenario tags its aggregate ids with a mnemonic hex segment so the
event store records remain traceable back to the scenario that wrote
them (e.g., `...000000350e01` for Argonne under the beta-alignment
scenario, `...000000352e01` under shakedown). The fixture must NOT pick
canonical UUIDs; it accepts whatever the caller declares as constants.

## Usage shape

```python
_DEVICES = (
    DeviceSpec("Aerotech_ABRS_rotary", _ASSET_ROTARY_ID, "RotaryStage", _CAP_ROTARY_ID),
    DeviceSpec("Sample_top_X",         _ASSET_LINEAR_ID, "LinearStage", _CAP_LINEAR_ID),
)

def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(
            principal_id=_PRINCIPAL_ID,
            argonne_id=_ARGONNE_ID,
            aps_site_id=_APS_ID,
            unit_id=_UNIT_ID,
            devices=_DEVICES,
        ),
        # ... scenario-specific ids follow
    ]

async def test_...(db_pool):
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    await install_aps_unit(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        argonne_id=_ARGONNE_ID,
        aps_site_id=_APS_ID,
        unit_id=_UNIT_ID,
        devices=_DEVICES,
        operator_name="2-BM Shakedown Operator",
    )
    # ... scenario-specific commands follow
```
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features.add_asset_capability import AddAssetCapability
from cora.equipment.features.add_asset_capability import bind as bind_add_capability
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.define_capability import bind as bind_define_capability
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.kernel import Kernel


@dataclass(frozen=True)
class DeviceSpec:
    """One Device under the Unit: its name, pre-allocated asset_id, the
    Capability it gets linked to, and that Capability's pre-allocated id."""

    name: str
    asset_id: UUID
    cap_name: str
    cap_id: UUID


@dataclass(frozen=True)
class FacilityIds:
    """IDs of every aggregate registered by `install_aps_unit()`.
    Returned for callers that want to reference them post-install without
    re-importing module-level constants."""

    principal_id: UUID
    argonne_id: UUID
    aps_site_id: UUID
    unit_id: UUID
    device_ids: tuple[UUID, ...]
    cap_ids: tuple[UUID, ...]


def facility_id_prefix(
    *,
    principal_id: UUID,
    argonne_id: UUID,
    aps_site_id: UUID,
    unit_id: UUID,
    devices: Sequence[DeviceSpec],
) -> list[UUID]:
    """FixedIdGenerator queue prefix for `install_aps_unit()`.

    Ordering mirrors the ceremony exactly:
      1. register_actor: principal_id, event
      2. register_asset Argonne: argonne_id, event
      3. register_asset APS: aps_site_id, event
      4. register_asset Unit: unit_id, event
      5. define_capability x N (in `devices` order): cap_id, event
      6. register_asset + add_asset_capability x N: asset_id, register_event, addcap_event

    Anonymous event ids use `uuid4()`. Total length = 8 + 5 * N device entries.
    """
    e = uuid4
    ids: list[UUID] = [
        principal_id,
        e(),
        argonne_id,
        e(),
        aps_site_id,
        e(),
        unit_id,
        e(),
    ]
    for d in devices:
        ids.extend([d.cap_id, e()])
    for d in devices:
        ids.extend([d.asset_id, e(), e()])
    return ids


async def install_aps_unit(
    deps: Kernel,
    *,
    principal_id: UUID,
    correlation_id: UUID,
    argonne_id: UUID,
    aps_site_id: UUID,
    unit_id: UUID,
    devices: Sequence[DeviceSpec],
    operator_name: str = "2-BM Operator",
    unit_name: str = "2-BM",
) -> FacilityIds:
    """Execute the canonical facility-install ceremony for a 2-BM-shape Unit.

    Order matches `facility_id_prefix()` exactly: actor, then
    Argonne -> APS -> Unit, then all Capabilities defined, then all
    Devices registered + their Capabilities linked.

    `unit_name` defaults to "2-BM" but parameterizes for future
    beamline scenarios (2-BM, 7-BM, etc.).
    """
    await bind_register_actor(deps)(
        RegisterActor(name=operator_name),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_register_asset(deps)(
        RegisterAsset(name="Argonne", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_register_asset(deps)(
        RegisterAsset(name="APS", level=AssetLevel.SITE, parent_id=argonne_id),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_register_asset(deps)(
        RegisterAsset(name=unit_name, level=AssetLevel.UNIT, parent_id=aps_site_id),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    for d in devices:
        await bind_define_capability(deps)(
            DefineCapability(name=d.cap_name),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
    for d in devices:
        await bind_register_asset(deps)(
            RegisterAsset(name=d.name, level=AssetLevel.DEVICE, parent_id=unit_id),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
        await bind_add_capability(deps)(
            AddAssetCapability(asset_id=d.asset_id, capability_id=d.cap_id),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
    return FacilityIds(
        principal_id=principal_id,
        argonne_id=argonne_id,
        aps_site_id=aps_site_id,
        unit_id=unit_id,
        device_ids=tuple(d.asset_id for d in devices),
        cap_ids=tuple(d.cap_id for d in devices),
    )


__all__ = [
    "DeviceSpec",
    "FacilityIds",
    "facility_id_prefix",
    "install_aps_unit",
]
