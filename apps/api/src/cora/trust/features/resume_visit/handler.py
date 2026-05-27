"""Application handler for the `resume_visit` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.resume_visit.command import ResumeVisit
from cora.trust.features.resume_visit.decider import decide


class Handler(Protocol):
    """Callable interface every resume_visit handler implements."""

    async def __call__(
        self,
        command: ResumeVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a resume_visit handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="ResumeVisit",
        log_prefix="resume_visit",
        decide_fn=decide,
    )
