"""Application handler for the `expire_clearance` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.expire_clearance.command import ExpireClearance
from cora.safety.features.expire_clearance.decider import decide


class Handler(Protocol):
    """Callable interface every expire_clearance handler implements."""

    async def __call__(
        self,
        command: ExpireClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an expire_clearance handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="ExpireClearance",
        log_prefix="expire_clearance",
        decide_fn=decide,
    )
