"""Application handler for the `submit_clearance` slice.

Update-style handler. Full canonical body lives in
`cora.safety._clearance_update_handler.make_clearance_update_handler`.
This module is a thin slice-specific bind. Not idempotency-wrapped:
strict-not-idempotent guard at the decider (re-submitting raises 409).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety._clearance_update_handler import make_clearance_update_handler
from cora.safety.features.submit_clearance.command import SubmitClearance
from cora.safety.features.submit_clearance.decider import decide


class Handler(Protocol):
    """Callable interface every submit_clearance handler implements."""

    async def __call__(
        self,
        command: SubmitClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a submit_clearance handler closed over the shared deps."""
    return make_clearance_update_handler(
        deps,
        command_name="SubmitClearance",
        log_prefix="submit_clearance",
        decide_fn=decide,
    )
