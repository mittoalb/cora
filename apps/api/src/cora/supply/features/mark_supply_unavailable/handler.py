"""Application handler for the `mark_supply_unavailable` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.supply._supply_update_handler import make_supply_update_handler
from cora.supply.features.mark_supply_unavailable.command import MarkSupplyUnavailable
from cora.supply.features.mark_supply_unavailable.decider import decide


class Handler(Protocol):
    """Callable interface every mark_supply_unavailable handler implements."""

    async def __call__(
        self,
        command: MarkSupplyUnavailable,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a mark_supply_unavailable handler closed over the shared deps."""
    return make_supply_update_handler(
        deps,
        command_name="MarkSupplyUnavailable",
        log_prefix="mark_supply_unavailable",
        decide_fn=decide,
    )
