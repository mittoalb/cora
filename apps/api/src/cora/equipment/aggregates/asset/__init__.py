"""Asset aggregate: state, level/lifecycle enums, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_asset/` and import from here for
state and event types.
"""

from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetCapabilityAdded,
    AssetCapabilityRemoved,
    AssetDecommissioned,
    AssetDegraded,
    AssetEvent,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetRestoredFromMaintenance,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.asset.evolver import evolve, fold
from cora.equipment.aggregates.asset.read import load_asset
from cora.equipment.aggregates.asset.state import (
    ASSET_NAME_MAX_LENGTH,
    Asset,
    AssetAlreadyExistsError,
    AssetCannotActivateError,
    AssetCannotAddCapabilityError,
    AssetCannotDecommissionError,
    AssetCannotEnterMaintenanceError,
    AssetCannotRelocateError,
    AssetCannotRemoveCapabilityError,
    AssetCannotRestoreFromMaintenanceError,
    AssetCondition,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    InvalidAssetNameError,
    InvalidAssetParentError,
)

__all__ = [
    "ASSET_NAME_MAX_LENGTH",
    "Asset",
    "AssetActivated",
    "AssetAlreadyExistsError",
    "AssetCannotActivateError",
    "AssetCannotAddCapabilityError",
    "AssetCannotDecommissionError",
    "AssetCannotEnterMaintenanceError",
    "AssetCannotRelocateError",
    "AssetCannotRemoveCapabilityError",
    "AssetCannotRestoreFromMaintenanceError",
    "AssetCapabilityAdded",
    "AssetCapabilityRemoved",
    "AssetCondition",
    "AssetDecommissioned",
    "AssetDegraded",
    "AssetEvent",
    "AssetFaulted",
    "AssetLevel",
    "AssetLifecycle",
    "AssetMaintenanceEntered",
    "AssetName",
    "AssetNotFoundError",
    "AssetRegistered",
    "AssetRelocated",
    "AssetRestored",
    "AssetRestoredFromMaintenance",
    "InvalidAssetNameError",
    "InvalidAssetParentError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_asset",
    "to_payload",
]
