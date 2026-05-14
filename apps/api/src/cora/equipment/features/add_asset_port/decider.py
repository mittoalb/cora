"""Pure decider for the `AddAssetPort` command (Phase 5h).

Two disqualifying conditions both surface as
`AssetCannotAddPortError` with a diagnostic `reason`:

  - asset is `Decommissioned` (retired; no further port changes)
  - port name already exists in `state.ports` (strict-not-idempotent;
    same precedent as Capability mutation)

The new port's value-object construction (AssetPort.__post_init__)
validates name + signal_type lengths and raises
`InvalidAssetPortNameError` / `InvalidAssetPortSignalTypeError` on
malformed values; the route's Pydantic body keeps these to 422 by
catching them at the boundary.

Lifecycle-independence note: 5g-b condition / 5g-c settings allow
mutations in any lifecycle state; ports follow the SAME stance for
declaration but reject when Decommissioned because port hardware
removal is more like a hierarchy change (5d Relocate also rejects
Decommissioned). Operator vocabulary: a Decommissioned asset is
out of inventory; you wouldn't be re-wiring it.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddPortError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetPort,
    AssetPortAdded,
)
from cora.equipment.features.add_asset_port.command import AddAssetPort


def decide(
    state: Asset | None,
    command: AddAssetPort,
    *,
    now: datetime,
) -> list[AssetPortAdded]:
    """Decide the events produced by adding a port to an existing Asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotAddPortError(
            state.id,
            command.port_name,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; port changes are not allowed)"
            ),
        )

    # Construct the AssetPort to validate name + signal_type shape.
    # InvalidAssetPortNameError / InvalidAssetPortSignalTypeError
    # propagate as 400 from the route's exception handler.
    proposed = AssetPort(
        name=command.port_name,
        direction=command.direction,
        signal_type=command.signal_type,
    )

    if any(p.name == proposed.name for p in state.ports):
        raise AssetCannotAddPortError(
            state.id,
            proposed.name,
            reason=(
                f"port name {proposed.name!r} is already in this asset's "
                "port set (strict-not-idempotent; remove the existing port "
                "first, or pick a different name)"
            ),
        )

    return [
        AssetPortAdded(
            asset_id=state.id,
            port_name=proposed.name,
            direction=proposed.direction.value,
            signal_type=proposed.signal_type,
            occurred_at=now,
        )
    ]
