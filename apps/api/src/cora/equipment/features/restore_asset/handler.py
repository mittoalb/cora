"""Application handler for the `restore_asset` slice.

Update-style handler. Delegates to
`make_asset_update_handler`.

Not idempotency-wrapped: condition transitions are
no-op-on-unchanged at the decider layer.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.restore_asset.command import RestoreAsset
from cora.equipment.features.restore_asset.decider import decide
from cora.infrastructure.kernel import Kernel

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every restore_asset handler implements."""

    async def __call__(
        self,
        command: RestoreAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a restore_asset handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="RestoreAsset",
        log_prefix="restore_asset",
        decide_fn=decide,
    )
