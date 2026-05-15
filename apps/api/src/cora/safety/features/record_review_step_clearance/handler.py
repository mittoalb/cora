"""Application handler for the `record_review_step_clearance` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.record_review_step_clearance.command import (
    RecordReviewStepClearance,
)
from cora.safety.features.record_review_step_clearance.decider import decide


class Handler(Protocol):
    """Callable interface every record_review_step_clearance handler implements."""

    async def __call__(
        self,
        command: RecordReviewStepClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a record_review_step_clearance handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="RecordReviewStepClearance",
        log_prefix="record_review_step_clearance",
        decide_fn=decide,
    )
