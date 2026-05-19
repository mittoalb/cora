"""Application handler for the `abort_run` slice.

Update-style handler. Canonical body lives in
`cora.run._update_handler.make_run_update_handler`; this module
is a thin slice-specific bind.

The command's `reason` field IS captured on the emitted
`RunAborted` event payload but is intentionally NOT logged at
the handler boundary (matches Subject discard / Asset condition
precedent), so this slice does not pass `extra_log_fields`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.run._update_handler import make_run_update_handler
from cora.run.features.abort_run.command import AbortRun
from cora.run.features.abort_run.decider import decide

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every abort_run handler implements."""

    async def __call__(
        self,
        command: AbortRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an abort_run handler closed over the shared deps."""
    return make_run_update_handler(
        deps,
        command_name="AbortRun",
        log_prefix="abort_run",
        decide_fn=decide,
    )
