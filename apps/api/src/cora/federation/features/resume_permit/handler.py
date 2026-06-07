"""Application handler for the `resume_permit` slice.

Update-style handler (loads the Permit aggregate then appends a
`PermitResumed` event).

Not idempotency-wrapped: transition handlers use the strict-not-
idempotent guard at the decider (resuming a non-Suspended permit
raises `PermitCannotResumeError` -> HTTP 409); HTTP-layer caching
adds no value for transitions.

Delegates to `make_permit_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `resumed_by`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_permit_update_handler
from cora.federation.features.resume_permit.command import ResumePermit
from cora.federation.features.resume_permit.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every resume_permit handler implements."""

    async def __call__(
        self,
        command: ResumePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a resume_permit handler closed over the shared deps."""
    return make_permit_update_handler(
        deps,
        command_name="ResumePermit",
        log_prefix="resume_permit",
        decide_fn=decide,
        actor_kwarg="resumed_by",
    )
