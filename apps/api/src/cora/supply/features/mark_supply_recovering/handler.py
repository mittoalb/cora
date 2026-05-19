"""Application handler for the `mark_supply_recovering` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.supply._supply_update_handler import make_supply_update_handler
from cora.supply.features.mark_supply_recovering.command import MarkSupplyRecovering
from cora.supply.features.mark_supply_recovering.decider import decide

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every mark_supply_recovering handler implements."""

    async def __call__(
        self,
        command: MarkSupplyRecovering,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a mark_supply_recovering handler closed over the shared deps."""
    return make_supply_update_handler(
        deps,
        command_name="MarkSupplyRecovering",
        log_prefix="mark_supply_recovering",
        decide_fn=decide,
    )
