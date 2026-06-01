"""Application handler for the `suspend_permit` slice.

Update-style handler (loads the Permit aggregate, validates the FSM
transition, appends a `PermitSuspended` event). NOT idempotency-
wrapped: transition handlers rely on the strict-not-idempotent guard
at the decider (re-suspending an already-Suspended permit raises
`PermitCannotSuspendError` -> HTTP 409); HTTP-layer caching adds no
value for transitions.

Delegates to `make_permit_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `suspended_by_actor_id`, then loads / authorizes / folds /
decides / appends through the shared body.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_permit_update_handler
from cora.federation.features.suspend_permit.command import SuspendPermit
from cora.federation.features.suspend_permit.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every suspend_permit handler implements."""

    async def __call__(
        self,
        command: SuspendPermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a suspend_permit handler closed over the shared deps."""
    return make_permit_update_handler(
        deps,
        command_name="SuspendPermit",
        log_prefix="suspend_permit",
        decide_fn=decide,
        actor_kwarg="suspended_by_actor_id",
    )
