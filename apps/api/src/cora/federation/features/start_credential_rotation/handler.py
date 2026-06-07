"""Application handler for the `start_credential_rotation` slice.

Update-style handler (loads the Credential aggregate, validates the
FSM transition, appends a `CredentialRotationStarted` event).

Not idempotency-wrapped at wire.py: start_credential_rotation is a
strict-not-idempotent transition (starting against an already-Rotating
or Revoked credential raises `CredentialCannotRotateError` -> HTTP
409); HTTP-layer caching adds no value when the decider rejects
replays.

Delegates to `make_credential_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `rotation_started_by`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_credential_update_handler
from cora.federation.features.start_credential_rotation.command import (
    StartCredentialRotation,
)
from cora.federation.features.start_credential_rotation.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every start_credential_rotation handler implements."""

    async def __call__(
        self,
        command: StartCredentialRotation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_credential_rotation handler closed over the shared deps."""
    return make_credential_update_handler(
        deps,
        command_name="StartCredentialRotation",
        log_prefix="start_credential_rotation",
        decide_fn=decide,
        actor_kwarg="rotation_started_by",
    )
