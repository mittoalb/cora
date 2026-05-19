"""Application handler for the `degrade_asset` slice.

Update-style handler. The full canonical body lives in
`cora.equipment._asset_update_handler.make_asset_update_handler`
(load + authorize + fold + decide + append, with structured logging
at each boundary). This module is a thin slice-specific bind.

Not idempotency-wrapped: condition transitions are
no-op-on-unchanged at the decider layer (second call with the same
target condition returns []); HTTP-layer caching adds no value.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.degrade_asset.command import DegradeAsset
from cora.equipment.features.degrade_asset.decider import decide
from cora.infrastructure.kernel import Kernel

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every degrade_asset handler implements."""

    async def __call__(
        self,
        command: DegradeAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a degrade_asset handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="DegradeAsset",
        log_prefix="degrade_asset",
        decide_fn=decide,
    )
