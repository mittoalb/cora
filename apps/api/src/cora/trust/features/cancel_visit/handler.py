"""Application handler for the `cancel_visit` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.cancel_visit.command import CancelVisit
from cora.trust.features.cancel_visit.decider import decide


class Handler(Protocol):
    """Callable interface every cancel_visit handler implements."""

    async def __call__(
        self,
        command: CancelVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a cancel_visit handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="CancelVisit",
        log_prefix="cancel_visit",
        decide_fn=decide,
    )
