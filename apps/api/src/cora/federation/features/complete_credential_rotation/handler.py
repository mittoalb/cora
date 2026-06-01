"""Application handler for the `complete_credential_rotation` slice.

Update-style handler (loads the Credential aggregate, validates the
FSM transition, appends a `CredentialRotationCompleted` event).

Not idempotency-wrapped at wire.py: completing a rotation is strict-
not-idempotent at the decider (completing on a non-Rotating credential
raises `CredentialCannotRotateError` -> HTTP 409); HTTP-layer caching
adds no value when the decider rejects replays.

Delegates to `make_credential_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `rotation_completed_by_actor_id`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_credential_update_handler
from cora.federation.features.complete_credential_rotation.command import (
    CompleteCredentialRotation,
)
from cora.federation.features.complete_credential_rotation.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every complete_credential_rotation handler implements."""

    async def __call__(
        self,
        command: CompleteCredentialRotation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a complete_credential_rotation handler closed over the shared deps."""
    return make_credential_update_handler(
        deps,
        command_name="CompleteCredentialRotation",
        log_prefix="complete_credential_rotation",
        decide_fn=decide,
        actor_kwarg="rotation_completed_by_actor_id",
    )
