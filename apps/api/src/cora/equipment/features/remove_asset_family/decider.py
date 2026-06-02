"""Pure decider for the `RemoveAssetFamily` command.

Mirror of `add_asset_family`'s decider. Two disqualifying
conditions both surface as `AssetCannotRemoveFamilyError`:

  - asset is `Decommissioned` (retired; no further family changes)
  - family_id NOT in `state.family_ids` (strict-not-idempotent;
    can't remove what isn't there)
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRemoveFamilyError,
    AssetFamilyRemoved,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.remove_asset_family.command import RemoveAssetFamily


def decide(
    state: Asset | None,
    command: RemoveAssetFamily,
    *,
    now: datetime,
) -> list[AssetFamilyRemoved]:
    """Decide the events produced by removing a family from an existing asset.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset must not be Decommissioned
        -> AssetCannotRemoveFamilyError
      - family_id must be in state.family_ids
        (strict-not-idempotent) -> AssetCannotRemoveFamilyError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotRemoveFamilyError(
            state.id,
            command.family_id,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; family changes are not allowed)"
            ),
        )

    if command.family_id not in state.family_ids:
        raise AssetCannotRemoveFamilyError(
            state.id,
            command.family_id,
            reason=(
                f"family {command.family_id} is not in this "
                "asset's family set (strict-not-idempotent)"
            ),
        )

    return [
        AssetFamilyRemoved(
            asset_id=state.id,
            family_id=command.family_id,
            occurred_at=now,
        )
    ]
