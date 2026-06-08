"""Application handler for the `start_seal_republishing` slice.

Update-style handler (loads the Seal aggregate, validates the FSM
transition, appends a `SealRepublishingStarted` event).

The Seal stream UUID is deterministic per facility: the handler
derives it via `seal_stream_id(facility_code)` (UUID5 over the canonical
federation namespace) so every Seal slice agrees on the same stream
identity for a given `facility_code`. The shared factory threads that
derivation through `resolve_stream_id`.

Not idempotency-wrapped at wire.py: start_seal_republishing is a
strict-not-idempotent transition (starting against an already
Republishing Seal raises `SealCannotStartRepublishingError` -> HTTP
409); HTTP-layer caching adds no value when the decider rejects
replays.

Single-stream append; no cross-BC writes. Republishing start is not
itself a security-touching event (the online key is unchanged and the
offline root is the only signer during the window), so no
DecisionRegistered companion event is emitted. The cross-BC audit
shape lands on `rotate_seal_online_key` where the online key actually
changes.

Delegates to `make_seal_update_handler` (Federation-local
actor-stamping factory) which threads `principal_id` into the decider
under `started_by`.
"""

from typing import Protocol
from uuid import UUID

from cora.federation._actor_update_handler import make_seal_update_handler
from cora.federation.features.start_seal_republishing.command import (
    StartSealRepublishing,
)
from cora.federation.features.start_seal_republishing.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every start_seal_republishing handler implements."""

    async def __call__(
        self,
        command: StartSealRepublishing,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_seal_republishing handler closed over the shared deps."""
    return make_seal_update_handler(
        deps,
        command_name="StartSealRepublishing",
        log_prefix="start_seal_republishing",
        decide_fn=decide,
        actor_kwarg="started_by",
    )
