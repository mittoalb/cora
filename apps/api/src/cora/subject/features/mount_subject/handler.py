"""Application handler for the `mount_subject` slice.

Update-style handler shape (mirror of `deactivate_actor.handler`):

    1. authorize(principal_id, command_name, conduit) -> Allow | Deny
    2. clock.now() -> domain timestamp
    3. event_store.load(stream_type, command.subject_id)
       -> (stored_events, current_version)
    4. fold([from_stored(s) for s in stored_events]) -> state
    5. decide(state, command, *, now) -> domain events
    6. wrap each domain event as a NewEvent (via aggregate's to_payload)
    7. event_store.append(stream_type, command.subject_id,
                          current_version, ...)

Differs from create-style:
  - Command carries the target aggregate id (caller-supplied).
  - Load + fold + decide instead of skipping the load.
  - expected_version=current_version (vs. 0 for create) — race-loser
    on concurrent writes raises ConcurrencyError, mapped to 409 by
    Access's globally-registered exception handler (Access boots
    first; subsequent BCs inherit the registration).
  - No new_id injected to decider; aggregate already exists.
  - Returns None (no new id).

Not idempotency-wrapped: update-style commands are inherently
idempotent at the domain level (second call hits
`SubjectCannotMountError`); apply only when cached-success-on-retry
semantics are needed. See CONTRIBUTING.md.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.subject.aggregates.subject import (
    SubjectEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.subject.errors import UnauthorizedError
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.decider import decide

_STREAM_TYPE = "Subject"
_COMMAND_NAME = "MountSubject"
_CONDUIT_DEFAULT = "default"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every mount_subject handler implements.

    See `register_subject.handler.Handler` for the rationale on the
    optional `causation_id` kwarg (HTTP / MCP entrypoints pass None;
    sagas / process managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: MountSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a mount_subject handler closed over the shared deps."""

    async def handler(
        command: MountSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "mount_subject.start",
            command_name=_COMMAND_NAME,
            subject_id=str(command.subject_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit=_CONDUIT_DEFAULT,
        )
        if isinstance(decision, Deny):
            _log.info(
                "mount_subject.denied",
                command_name=_COMMAND_NAME,
                subject_id=str(command.subject_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.subject_id,
        )
        history: list[SubjectEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(state=state, command=command, now=now)

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.subject_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "mount_subject.success",
            command_name=_COMMAND_NAME,
            subject_id=str(command.subject_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
