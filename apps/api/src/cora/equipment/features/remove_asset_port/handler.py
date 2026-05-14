"""Application handler for the `remove_asset_port` slice (Phase 5h)."""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.remove_asset_port.command import RemoveAssetPort
from cora.equipment.features.remove_asset_port.decider import decide
from cora.infrastructure.kernel import Kernel


class Handler(Protocol):
    """Callable interface every remove_asset_port handler implements."""

    async def __call__(
        self,
        command: RemoveAssetPort,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a remove_asset_port handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="RemoveAssetPort",
        log_prefix="remove_asset_port",
        decide_fn=decide,
    )
