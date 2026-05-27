"""Application handler for the `arrive_visit` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.trust._visit_update_handler.make_visit_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.arrive_visit.command import ArriveVisit
from cora.trust.features.arrive_visit.decider import decide


class Handler(Protocol):
    """Callable interface every arrive_visit handler implements."""

    async def __call__(
        self,
        command: ArriveVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an arrive_visit handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="ArriveVisit",
        log_prefix="arrive_visit",
        decide_fn=decide,
    )
