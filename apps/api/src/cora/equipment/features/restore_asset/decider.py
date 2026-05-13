"""Pure decider for the `RestoreAsset` command.

Target-state transition: any condition -> Nominal. Mirror of
`degrade_asset.decide` with target NOMINAL. Lifecycle is NOT gated.

Invariants:
  - State must not be None (asset must exist) -> AssetNotFoundError
  - No-op on unchanged: if current condition is already Nominal,
    return [] (matches 5g-a's no-op-on-unchanged precedent).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetNotFoundError,
    AssetRestored,
)
from cora.equipment.features.restore_asset.command import RestoreAsset


def decide(
    state: Asset | None,
    command: RestoreAsset,
    *,
    now: datetime,
) -> list[AssetRestored]:
    """Decide the events produced by restoring an existing asset to Nominal."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.condition is AssetCondition.NOMINAL:
        return []
    return [AssetRestored(asset_id=state.id, reason=command.reason, occurred_at=now)]
