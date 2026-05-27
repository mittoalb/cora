"""Application handler for the `complete_visit` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.complete_visit.command import CompleteVisit
from cora.trust.features.complete_visit.decider import decide


class Handler(Protocol):
    """Callable interface every complete_visit handler implements."""

    async def __call__(
        self,
        command: CompleteVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a complete_visit handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="CompleteVisit",
        log_prefix="complete_visit",
        decide_fn=decide,
    )
