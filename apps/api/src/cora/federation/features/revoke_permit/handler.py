"""Application handler for the `revoke_permit` slice.

Update-style handler (loads the Permit aggregate then appends a
`PermitRevoked` event).

Not idempotency-wrapped at wire.py: revoke is a strict-not-idempotent
transition (re-revoking raises `PermitCannotRevokeError` -> HTTP 409);
HTTP-layer caching adds no value when the decider rejects replays.

Delegates to `make_permit_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `revoked_by_actor_id`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_permit_update_handler
from cora.federation.features.revoke_permit.command import RevokePermit
from cora.federation.features.revoke_permit.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every revoke_permit handler implements."""

    async def __call__(
        self,
        command: RevokePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a revoke_permit handler closed over the shared deps."""
    return make_permit_update_handler(
        deps,
        command_name="RevokePermit",
        log_prefix="revoke_permit",
        decide_fn=decide,
        actor_kwarg="revoked_by_actor_id",
    )
