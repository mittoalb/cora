"""Application handler for the `sign_seal_pointer` slice.

Longhand update handler (mirrors `start_credential_rotation` /
`revoke_permit`): the decider needs handler-injected `signed_by_actor_id`
to stamp the audit denorm onto `SealPointerSigned`, so this slice
cannot use the `make_update_handler` factory (which only forwards
`state`, `command`, `now`). The longhand body wraps the same
load-authorize-fold-decide-append sequence.

Singleton stream identity: the Seal aggregate is keyed by `facility_id`
(str) but the event store keys streams by UUID. The handler derives a
deterministic stream UUID via `seal_stream_id(facility_id)` (UUID5 over
the canonical federation namespace) so the same facility always maps
to the same stream and every Seal slice agrees on stream identity for
a given `facility_id`.

Not idempotency-wrapped at wire.py: sign_seal_pointer is a strict-not-
idempotent transition (signing from a non-Live posture raises
`SealCannotSignError` -> HTTP 409; supplying a non-monotonic sequence
raises `SealSequenceNumberRegressionError` -> HTTP 409); HTTP-layer
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
from cora.federation.features.sign_seal_pointer.command import SignSealPointer
from cora.federation.features.sign_seal_pointer.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Seal"
_COMMAND_NAME = "SignSealPointer"

_log = get_logger(__name__)


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

    async def handler(
        command: SignSealPointer,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "sign_seal_pointer.start",
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
                "sign_seal_pointer.denied",
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
            signed_by_actor_id=principal_id,
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
            "sign_seal_pointer.success",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
