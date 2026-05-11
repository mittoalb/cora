"""Pure decider for the `RemoveAssetCapability` command.

Mirror of `add_asset_capability`'s decider. Two disqualifying
conditions both surface as `AssetCannotRemoveCapabilityError`:

  - asset is `Decommissioned` (retired; no further capability changes)
  - capability_id NOT in `state.capabilities` (strict-not-idempotent;
    can't remove what isn't there)
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRemoveCapabilityError,
    AssetCapabilityRemoved,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.remove_asset_capability.command import RemoveAssetCapability


def decide(
    state: Asset | None,
    command: RemoveAssetCapability,
    *,
    now: datetime,
) -> list[AssetCapabilityRemoved]:
    """Decide the events produced by removing a capability from an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotRemoveCapabilityError(
            state.id,
            command.capability_id,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; capability changes are not allowed)"
            ),
        )

    if command.capability_id not in state.capabilities:
        raise AssetCannotRemoveCapabilityError(
            state.id,
            command.capability_id,
            reason=(
                f"capability {command.capability_id} is not in this "
                "asset's capability set (strict-not-idempotent)"
            ),
        )

    return [
        AssetCapabilityRemoved(
            asset_id=state.id,
            capability_id=command.capability_id,
            occurred_at=now,
        )
    ]
