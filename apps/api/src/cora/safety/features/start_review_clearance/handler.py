"""Application handler for the `start_review_clearance` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.start_review_clearance.command import StartReviewClearance
from cora.safety.features.start_review_clearance.decider import decide


class Handler(Protocol):
    """Callable interface every start_review_clearance handler implements."""

    async def __call__(
        self,
        command: StartReviewClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_review_clearance handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="StartReviewClearance",
        log_prefix="start_review_clearance",
        decide_fn=decide,
    )
