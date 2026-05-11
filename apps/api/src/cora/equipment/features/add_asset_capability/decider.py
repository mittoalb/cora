"""Pure decider for the `AddAssetCapability` command.

Capability mutation, not a lifecycle transition. Two disqualifying
conditions both surface as `AssetCannotAddCapabilityError` with a
diagnostic `reason` string:

  - asset is `Decommissioned` (retired; no further capability changes)
  - capability_id already in `state.capabilities` (strict-not-idempotent;
    same precedent as activate / mount-second-call-raises)

Mirrors `AssetCannotRelocateError`'s collapsed-conditions pattern.
The decider does NOT verify the referenced Capability id refers to
a real Capability stream (eventual-consistency stance per Trust 3b
precedent); mismatch surfaces at Plan binding (6e).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddCapabilityError,
    AssetCapabilityAdded,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.add_asset_capability.command import AddAssetCapability


def decide(
    state: Asset | None,
    command: AddAssetCapability,
    *,
    now: datetime,
) -> list[AssetCapabilityAdded]:
    """Decide the events produced by adding a capability to an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotAddCapabilityError(
            state.id,
            command.capability_id,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; capability changes are not allowed)"
            ),
        )

    if command.capability_id in state.capabilities:
        raise AssetCannotAddCapabilityError(
            state.id,
            command.capability_id,
            reason=(
                f"capability {command.capability_id} is already in this "
                "asset's capability set (strict-not-idempotent)"
            ),
        )

    return [
        AssetCapabilityAdded(
            asset_id=state.id,
            capability_id=command.capability_id,
            occurred_at=now,
        )
    ]
