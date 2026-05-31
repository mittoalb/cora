"""Mount aggregate: the named slot in the beamline.

A `Mount` is the slot at which a specimen Asset sits. The slot
persists across installs (SAP's "the slot outlives the device
installed in it" lesson per project_mount_frame_design.md):
operators install / uninstall Assets into the slot, and the Mount
carries the slot's identity (`slot_code`), position (`Placement`
against a Frame), and currently-installed specimen
(`installed_asset_id: AssetId | None`).

Mounts form a tree via `parent_mount_id` (Assembly slot containing
Device slots, ISA-88-derived); the coordinate-frame parent is a
separate axis on `Placement.parent_frame` (which references a Frame,
NOT another Mount).

Lifecycle: `Active | Decommissioned`. `decommission_mount` is
guarded by `MountHasInstalledAsset` + `MountHasActiveChildren`
preconditions (no implicit eviction, no cascade).

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_mount/` (register / decommission /
update_mount_placement) plus the asset-install pair under
`cora.equipment.features.<verb>_asset/` (install_asset /
uninstall_asset; these operate on Mount streams to mutate
`installed_asset_id`).
"""

from cora.equipment.aggregates.mount.events import (
    MountAssetInstalled,
    MountAssetUninstalled,
    MountDecommissioned,
    MountEvent,
    MountPlacementUpdated,
    MountRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.mount.evolver import evolve, fold
from cora.equipment.aggregates.mount.read import load_mount
from cora.equipment.aggregates.mount.state import (
    SLOT_CODE_MAX_LENGTH,
    AssetAlreadyInstalledElsewhereError,
    AssetNotFoundForMountError,
    AssetNotInstallableError,
    InvalidSlotCodeError,
    Mount,
    MountAlreadyExistsError,
    MountAlreadyOccupiedError,
    MountCannotDecommissionError,
    MountCannotUpdateError,
    MountHasActiveChildrenError,
    MountHasInstalledAssetError,
    MountIsEmptyError,
    MountNotFoundError,
    MountStatus,
    SlotCode,
)

__all__ = [
    "SLOT_CODE_MAX_LENGTH",
    "AssetAlreadyInstalledElsewhereError",
    "AssetNotFoundForMountError",
    "AssetNotInstallableError",
    "InvalidSlotCodeError",
    "Mount",
    "MountAlreadyExistsError",
    "MountAlreadyOccupiedError",
    "MountAssetInstalled",
    "MountAssetUninstalled",
    "MountCannotDecommissionError",
    "MountCannotUpdateError",
    "MountDecommissioned",
    "MountEvent",
    "MountHasActiveChildrenError",
    "MountHasInstalledAssetError",
    "MountIsEmptyError",
    "MountNotFoundError",
    "MountPlacementUpdated",
    "MountRegistered",
    "MountStatus",
    "SlotCode",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_mount",
    "to_payload",
]
