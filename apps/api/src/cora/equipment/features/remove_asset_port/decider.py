"""Pure decider for the `RemoveAssetPort` command (Phase 5h).

Mirror of `add_asset_port.decide`. Two disqualifying conditions
both surface as `AssetCannotRemovePortError`:

  - asset is `Decommissioned` (retired)
  - no port with the given name in `state.ports` (strict-not-
    idempotent; symmetric with add)
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRemovePortError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetPortRemoved,
)
from cora.equipment.features.remove_asset_port.command import RemoveAssetPort


def decide(
    state: Asset | None,
    command: RemoveAssetPort,
    *,
    now: datetime,
) -> list[AssetPortRemoved]:
    """Decide the events produced by removing a port from an existing Asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    # Trim before lookup. Stored port names are canonicalized via
    # the AssetPort VO's __post_init__; honoring the same convention
    # on remove keeps add/remove symmetric and prevents whitespace
    # surprises from the route boundary.
    name = command.port_name.strip()

    if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotRemovePortError(
            state.id,
            name,
            reason=(
                f"asset is currently {AssetLifecycle.DECOMMISSIONED.value} "
                "(retired from service; port changes are not allowed)"
            ),
        )

    if not any(p.name == name for p in state.ports):
        raise AssetCannotRemovePortError(
            state.id,
            name,
            reason=(
                f"port name {name!r} is not in this asset's "
                "port set (strict-not-idempotent; cannot remove a port "
                "that does not exist)"
            ),
        )

    return [
        AssetPortRemoved(
            asset_id=state.id,
            port_name=name,
            occurred_at=now,
        )
    ]
