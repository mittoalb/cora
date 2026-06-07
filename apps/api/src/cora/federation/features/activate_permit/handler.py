"""Application handler for the `activate_permit` slice.

Update-style handler (loads the Permit aggregate, then appends a
`PermitActivated` event).

Not idempotency-wrapped: transition handlers use the
strict-not-idempotent guard at the decider (re-activating an already
non-Defined permit raises `PermitCannotActivateError` -> HTTP 409);
HTTP-layer caching adds no value for transitions.

Delegates to `make_permit_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `activated_by`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_permit_update_handler
from cora.federation.features.activate_permit.command import ActivatePermit
from cora.federation.features.activate_permit.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every activate_permit handler implements."""

    async def __call__(
        self,
        command: ActivatePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an activate_permit handler closed over the shared deps."""
    return make_permit_update_handler(
        deps,
        command_name="ActivatePermit",
        log_prefix="activate_permit",
        decide_fn=decide,
        actor_kwarg="activated_by",
    )
