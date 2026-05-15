"""Application handler for the `reject_clearance` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.reject_clearance.command import RejectClearance
from cora.safety.features.reject_clearance.decider import decide


class Handler(Protocol):
    """Callable interface every reject_clearance handler implements."""

    async def __call__(
        self,
        command: RejectClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a reject_clearance handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="RejectClearance",
        log_prefix="reject_clearance",
        decide_fn=decide,
    )
