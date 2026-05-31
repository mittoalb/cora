"""Application handler for the `complete_seal_republishing` slice.

Longhand update handler (mirrors `complete_credential_rotation`): the
decider needs handler-injected `completed_by_actor_id` to stamp the
audit denorm onto `SealRepublishingCompleted`, so this slice cannot
use the `make_update_handler` factory (which only forwards `state`,
`command`, `now`). The longhand body wraps the same
load-authorize-fold-decide-append sequence.

The Seal is a per-facility singleton; the handler derives the stream
UUID deterministically via `seal_stream_id(facility_id)` (UUID5 over
the canonical federation namespace) so every Seal slice agrees on the
same stream identity for the same `facility_id`.

Not idempotency-wrapped at wire.py: completing a republish is strict-
not-idempotent at the decider (completing on a non-Republishing Seal
raises `SealCannotCompleteRepublishingError` -> HTTP 409); HTTP-layer
caching adds no value when the decider rejects replays.
"""

from typing import Protocol
from uuid import UUID

from cora.federation.aggregates.seal import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features.complete_seal_republishing.command import (
    CompleteSealRepublishing,
)
from cora.federation.features.complete_seal_republishing.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Seal"
_COMMAND_NAME = "CompleteSealRepublishing"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every complete_seal_republishing handler implements."""

    async def __call__(
        self,
        command: CompleteSealRepublishing,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a complete_seal_republishing handler closed over the shared deps."""

    async def handler(
        command: CompleteSealRepublishing,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "complete_seal_republishing.start",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "complete_seal_republishing.denied",
                command_name=_COMMAND_NAME,
                facility_id=command.facility_id,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stream_id = seal_stream_id(command.facility_id)
        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=stream_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            completed_by_actor_id=principal_id,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=stream_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "complete_seal_republishing.success",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
