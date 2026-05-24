"""Application handler for the `complete_run` slice.

Update-style handler. Canonical body lives in
`cora.run._run_update_handler.make_run_update_handler`; this module
is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run._run_update_handler import make_run_update_handler
from cora.run.features.complete_run.command import CompleteRun
from cora.run.features.complete_run.decider import decide


class Handler(Protocol):
    """Callable interface every complete_run handler implements."""

    async def __call__(
        self,
        command: CompleteRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a complete_run handler closed over the shared deps."""
    return make_run_update_handler(
        deps,
        command_name="CompleteRun",
        log_prefix="complete_run",
        decide_fn=decide,
    )
