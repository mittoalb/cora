"""Application handler for the `abort_credential_rotation` slice.

Update-style handler (loads the Credential aggregate, validates the
FSM transition, appends a `CredentialRotationAborted` event). NOT
idempotency-wrapped: transition handlers rely on the
strict-not-idempotent guard at the decider (aborting a rotation on a
credential not in `Rotating` raises `CredentialCannotRotateError`
-> HTTP 409); HTTP-layer caching adds no value for transitions.

Delegates to `make_credential_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `rotation_aborted_by`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_credential_update_handler
from cora.federation.features.abort_credential_rotation.command import (
    AbortCredentialRotation,
)
from cora.federation.features.abort_credential_rotation.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every abort_credential_rotation handler implements."""

    async def __call__(
        self,
        command: AbortCredentialRotation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an abort_credential_rotation handler closed over the shared deps."""
    return make_credential_update_handler(
        deps,
        command_name="AbortCredentialRotation",
        log_prefix="abort_credential_rotation",
        decide_fn=decide,
        actor_kwarg="rotation_aborted_by",
    )
