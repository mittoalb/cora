"""Application handler for the `start_clearance_review` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.start_clearance_review.command import StartClearanceReview
from cora.safety.features.start_clearance_review.decider import decide


class Handler(Protocol):
    """Callable interface every start_clearance_review handler implements."""

    async def __call__(
        self,
        command: StartClearanceReview,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_clearance_review handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="StartClearanceReview",
        log_prefix="start_clearance_review",
        decide_fn=decide,
    )
