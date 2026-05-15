"""Application handler for the `restore_supply` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.supply._supply_update_handler import make_supply_update_handler
from cora.supply.features.restore_supply.command import RestoreSupply
from cora.supply.features.restore_supply.decider import decide


class Handler(Protocol):
    """Callable interface every restore_supply handler implements."""

    async def __call__(
        self,
        command: RestoreSupply,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a restore_supply handler closed over the shared deps."""
    return make_supply_update_handler(
        deps,
        command_name="RestoreSupply",
        log_prefix="restore_supply",
        decide_fn=decide,
    )
