"""Application handler for the `deregister_supply` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.supply._supply_update_handler import make_supply_update_handler
from cora.supply.features.deregister_supply.command import DeregisterSupply
from cora.supply.features.deregister_supply.decider import decide


class Handler(Protocol):
    """Callable interface every deregister_supply handler implements."""

    async def __call__(
        self,
        command: DeregisterSupply,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deregister_supply handler closed over the shared deps."""
    return make_supply_update_handler(
        deps,
        command_name="DeregisterSupply",
        log_prefix="deregister_supply",
        decide_fn=decide,
    )
