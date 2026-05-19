"""Application handler for the `approve_clearance` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.approve_clearance.command import ApproveClearance
from cora.safety.features.approve_clearance.decider import decide


class Handler(Protocol):
    """Callable interface every approve_clearance handler implements."""

    async def __call__(
        self,
        command: ApproveClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an approve_clearance handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="ApproveClearance",
        log_prefix="approve_clearance",
        decide_fn=decide,
    )
