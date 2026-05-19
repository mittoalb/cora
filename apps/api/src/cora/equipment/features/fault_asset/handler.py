"""Application handler for the `fault_asset` slice.

Update-style handler. Delegates to
`make_asset_update_handler` (load + authorize + fold + decide +
append, with structured logging at each boundary).

Not idempotency-wrapped: condition transitions are
no-op-on-unchanged at the decider layer.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.fault_asset.command import FaultAsset
from cora.equipment.features.fault_asset.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every fault_asset handler implements."""

    async def __call__(
        self,
        command: FaultAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a fault_asset handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="FaultAsset",
        log_prefix="fault_asset",
        decide_fn=decide,
    )
