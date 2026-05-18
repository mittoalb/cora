"""Pure decider for the `RemoveAssetFamily` command.

Mirror of `add_asset_family`'s decider. Two disqualifying
conditions both surface as `AssetCannotRemoveFamilyError`:

  - asset is `Decommissioned` (retired; no further capability changes)
  - family_id NOT in `state.families` (strict-not-idempotent;
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
    """Decide the events produced by removing a capability from an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotRemoveFamilyError(
            state.id,
            command.family_id,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; capability changes are not allowed)"
            ),
        )

    if command.family_id not in state.families:
        raise AssetCannotRemoveFamilyError(
            state.id,
            command.family_id,
            reason=(
                f"capability {command.family_id} is not in this "
                "asset's capability set (strict-not-idempotent)"
            ),
        )

    return [
        AssetFamilyRemoved(
            asset_id=state.id,
            family_id=command.family_id,
            occurred_at=now,
        )
    ]
