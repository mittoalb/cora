"""Pure decider for the `DegradeAsset` command.

Target-state transition: any condition -> Degraded. Lifecycle is
NOT gated; condition transitions are valid in any lifecycle state
(including Decommissioned, for honesty about device-state-in-storage).

Invariants:
  - State must not be None (asset must exist) -> AssetNotFoundError
  - No-op on unchanged: if current condition is already Degraded,
    return [] (matches 5g-a's no-op-on-unchanged precedent for
    `update_capability_schema`). Reason changes alone do NOT emit a
    new event; reason updates belong in a future Asset logbook.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetDegraded,
    AssetNotFoundError,
)
from cora.equipment.features.degrade_asset.command import DegradeAsset


def decide(
    state: Asset | None,
    command: DegradeAsset,
    *,
    now: datetime,
) -> list[AssetDegraded]:
    """Decide the events produced by degrading an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.condition is AssetCondition.DEGRADED:
        return []
    return [AssetDegraded(asset_id=state.id, reason=command.reason, occurred_at=now)]
