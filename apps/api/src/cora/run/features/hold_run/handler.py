"""Application handler for the `hold_run` slice.

Update-style handler. Canonical body lives in
`cora.run._update_handler.make_run_update_handler`; this module
is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.run._update_handler import make_run_update_handler
from cora.run.features.hold_run.command import HoldRun
from cora.run.features.hold_run.decider import decide

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every hold_run handler implements."""

    async def __call__(
        self,
        command: HoldRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a hold_run handler closed over the shared deps."""
    return make_run_update_handler(
        deps,
        command_name="HoldRun",
        log_prefix="hold_run",
        decide_fn=decide,
    )
