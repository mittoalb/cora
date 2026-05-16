"""Application handler for the `append_clearance_review_step` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.append_clearance_review_step.command import (
    AppendClearanceReviewStep,
)
from cora.safety.features.append_clearance_review_step.decider import decide


class Handler(Protocol):
    """Callable interface every append_clearance_review_step handler implements."""

    async def __call__(
        self,
        command: AppendClearanceReviewStep,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a append_clearance_review_step handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="AppendClearanceReviewStep",
        log_prefix="append_clearance_review_step",
        decide_fn=decide,
    )
