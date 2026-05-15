"""Application handler for the `begin_review_clearance` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.begin_review_clearance.command import BeginReviewClearance
from cora.safety.features.begin_review_clearance.decider import decide


class Handler(Protocol):
    """Callable interface every begin_review_clearance handler implements."""

    async def __call__(
        self,
        command: BeginReviewClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a begin_review_clearance handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="BeginReviewClearance",
        log_prefix="begin_review_clearance",
        decide_fn=decide,
    )
