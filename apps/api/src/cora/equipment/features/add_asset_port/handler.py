"""Application handler for the `add_asset_port` slice.

Update-style handler. The full canonical body lives in
`make_asset_update_handler` (load + authorize + fold + decide +
append, with structured logging). This module is a thin slice-
specific bind.

Not idempotency-wrapped: port-mutation is strict-not-idempotent at
the decider (second add hits AssetCannotAddPortError); apply only
when cached-success-on-retry semantics are needed.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.add_asset_port.command import AddAssetPort
from cora.equipment.features.add_asset_port.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every add_asset_port handler implements."""

    async def __call__(
        self,
        command: AddAssetPort,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an add_asset_port handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="AddAssetPort",
        log_prefix="add_asset_port",
        decide_fn=decide,
    )
