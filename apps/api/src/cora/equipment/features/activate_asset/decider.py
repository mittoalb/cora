"""Pure decider for the `ActivateAsset` command.

Update-style decider: receives the rebuilt `Asset` state (folded
from the loaded event stream) and returns the events to append.
No I/O.

Invariants:
  - State must not be None (asset must exist) -> AssetNotFoundError
  - State must be in `Commissioned` (the only state from which
    activation is valid) -> AssetCannotActivateError(current_lifecycle=...)

Strict semantics, not idempotent: re-activating an already-`Active`
asset raises rather than no-op or always-emit. Same precedent as
`mount_subject` / `measure_subject` / `deactivate_actor`.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetActivated,
    AssetCannotActivateError,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features.activate_asset.command import ActivateAsset


def decide(
    state: Asset | None,
    command: ActivateAsset,
    *,
    now: datetime,
) -> list[AssetActivated]:
    """Decide the events produced by activating an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.lifecycle is not AssetLifecycle.COMMISSIONED:
        raise AssetCannotActivateError(state.id, current_lifecycle=state.lifecycle)
    return [AssetActivated(asset_id=state.id, occurred_at=now)]
