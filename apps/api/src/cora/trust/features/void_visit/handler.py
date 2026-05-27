"""Application handler for the `void_visit` slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.void_visit.command import VoidVisit
from cora.trust.features.void_visit.decider import decide


class Handler(Protocol):
    """Callable interface every void_visit handler implements."""

    async def __call__(
        self,
        command: VoidVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a void_visit handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="VoidVisit",
        log_prefix="void_visit",
        decide_fn=decide,
    )
