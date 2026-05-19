"""Application handler for the `decommission_asset` slice.

Update-style handler. The full canonical body lives in
`cora.equipment._asset_update_handler.make_asset_update_handler`
(load + authorize + fold + decide + append, with structured logging
at each boundary). This module is a thin slice-specific bind: it
supplies the command name, log prefix, and decider.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent at the aggregate level (second decommission hits
`AssetCannotDecommissionError`); apply only when
cached-success-on-retry semantics are needed.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.decommission_asset.command import DecommissionAsset
from cora.equipment.features.decommission_asset.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every decommission_asset handler implements."""

    async def __call__(
        self,
        command: DecommissionAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a decommission_asset handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="DecommissionAsset",
        log_prefix="decommission_asset",
        decide_fn=decide,
    )
