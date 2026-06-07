"""Application handler for the `sign_seal_pointer` slice.

Update-style handler (loads the Seal aggregate, validates posture +
sequence-number monotonicity, appends a `SealPointerSigned` event).

Singleton stream identity: the Seal aggregate is keyed by `facility_id`
(str) but the event store keys streams by UUID. The handler derives a
deterministic stream UUID via `seal_stream_id(facility_id)` (UUID5 over
the canonical federation namespace) so the same facility always maps
to the same stream. The shared factory threads that derivation through
`resolve_stream_id`.

Not idempotency-wrapped at wire.py: sign_seal_pointer is a strict-not-
idempotent transition (signing from a non-Live posture raises
`SealCannotSignError` -> HTTP 409; supplying a non-monotonic sequence
raises `SealSequenceNumberRegressionError` -> HTTP 409); HTTP-layer
caching adds no value when the decider rejects replays.

Delegates to `make_seal_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `signed_by`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_seal_update_handler
from cora.federation.features.sign_seal_pointer.command import SignSealPointer
from cora.federation.features.sign_seal_pointer.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every sign_seal_pointer handler implements."""

    async def __call__(
        self,
        command: SignSealPointer,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a sign_seal_pointer handler closed over the shared deps."""
    return make_seal_update_handler(
        deps,
        command_name="SignSealPointer",
        log_prefix="sign_seal_pointer",
        decide_fn=decide,
        actor_kwarg="signed_by",
    )
