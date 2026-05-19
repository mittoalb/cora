"""Application handler for the `degrade_supply` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.supply._supply_update_handler.make_supply_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.supply._supply_update_handler import make_supply_update_handler
from cora.supply.features.degrade_supply.command import DegradeSupply
from cora.supply.features.degrade_supply.decider import decide

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every degrade_supply handler implements."""

    async def __call__(
        self,
        command: DegradeSupply,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a degrade_supply handler closed over the shared deps."""
    return make_supply_update_handler(
        deps,
        command_name="DegradeSupply",
        log_prefix="degrade_supply",
        decide_fn=decide,
    )
