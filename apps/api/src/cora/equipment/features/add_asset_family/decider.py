"""Pure decider for the `AddAssetFamily` command.

Family mutation, not a lifecycle transition. Two disqualifying
conditions both surface as `AssetCannotAddFamilyError` with a
diagnostic `reason` string:

  - asset is `Decommissioned` (retired; no further family changes)
  - family_id already in `state.family_ids` (strict-not-idempotent;
    same precedent as activate / mount-second-call-raises)

Mirrors `AssetCannotRelocateError`'s collapsed-conditions pattern.
The decider does NOT verify the referenced Family id refers to
a real Family stream (eventual-consistency stance per Trust 3b
precedent); mismatch surfaces at Plan binding (6e).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddFamilyError,
    AssetFamilyAdded,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.add_asset_family.command import AddAssetFamily


def decide(
    state: Asset | None,
    command: AddAssetFamily,
    *,
    now: datetime,
) -> list[AssetFamilyAdded]:
    """Decide the events produced by adding a family to an existing asset.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset must not be Decommissioned -> AssetCannotAddFamilyError
      - family_id must not already be in state.family_ids
        (strict-not-idempotent) -> AssetCannotAddFamilyError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotAddFamilyError(
            state.id,
            command.family_id,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; family changes are not allowed)"
            ),
        )

    if command.family_id in state.family_ids:
        raise AssetCannotAddFamilyError(
            state.id,
            command.family_id,
            reason=(
                f"family {command.family_id} is already in this "
                "asset's family set (strict-not-idempotent)"
            ),
        )

    return [
        AssetFamilyAdded(
            asset_id=state.id,
            family_id=command.family_id,
            occurred_at=now,
        )
    ]
