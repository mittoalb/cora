"""Application handler for the `activate_asset` slice.

Update-style handler. The full canonical body lives in
`cora.equipment._asset_update_handler.make_asset_update_handler`
(load + authorize + fold + decide + append, with structured logging
at each boundary). This module is a thin slice-specific bind: it
supplies the command name, log prefix, and decider.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent at the aggregate level (second activation hits
`AssetCannotActivateError`); apply only when cached-success-on-retry
semantics are needed.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.activate_asset.command import ActivateAsset
from cora.equipment.features.activate_asset.decider import decide
from cora.infrastructure.kernel import Kernel

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every activate_asset handler implements."""

    async def __call__(
        self,
        command: ActivateAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an activate_asset handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="ActivateAsset",
        log_prefix="activate_asset",
        decide_fn=decide,
    )
