"""Pure decider for the `DecommissionAsset` command.

Multi-source-state transition: `Commissioned | Active | Maintenance
-> Decommissioned`. Each source state is valid:

  - Commissioned: asset never went into service (operator changed
    mind, decommissioning before activation).
  - Active: asset retired from service (typical case).
  - Maintenance: asset retired during a maintenance window
    (operator decided not to bring it back into service).

Source-state guard uses tuple-membership rather than a
match-statement: the check is "is in {Commissioned, Active,
Maintenance}", which is naturally a set-membership test. Matches
the precedent locked by Subject's `remove_subject` decider.

Invariants:
  - State must not be None -> AssetNotFoundError
  - State.lifecycle must be in {Commissioned, Active, Maintenance}
    -> AssetCannotDecommissionError(current_lifecycle=...)
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotDecommissionError,
    AssetDecommissioned,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.decommission_asset.command import DecommissionAsset

_DECOMMISSIONABLE_LIFECYCLES: tuple[AssetLifecycle, ...] = (
    AssetLifecycle.COMMISSIONED,
    AssetLifecycle.ACTIVE,
    AssetLifecycle.MAINTENANCE,
)


def decide(
    state: Asset | None,
    command: DecommissionAsset,
    *,
    now: datetime,
) -> list[AssetDecommissioned]:
    """Decide the events produced by decommissioning an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.lifecycle not in _DECOMMISSIONABLE_LIFECYCLES:
        raise AssetCannotDecommissionError(state.id, current_lifecycle=state.lifecycle)
    return [AssetDecommissioned(asset_id=state.id, occurred_at=now)]
