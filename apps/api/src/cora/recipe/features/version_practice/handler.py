"""Application handler for the `version_practice` slice.

Update-style handler shape — load + fold + decide + append. Not
idempotency-wrapped (re-versioning with the same tag is allowed by
design — see decider docstring).

**Stays longhand**: command carries `version_tag` in addition to
`practice_id`, and the handler logs it for diagnostic visibility.
Same justification as version_method / version_capability.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.practice import (
    PracticeEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.version_practice.command import VersionPractice
from cora.recipe.features.version_practice.decider import decide

_STREAM_TYPE = "Practice"
_COMMAND_NAME = "VersionPractice"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every version_practice handler implements."""

    async def __call__(
        self,
        command: VersionPractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a version_practice handler closed over the shared deps."""

    async def handler(
        command: VersionPractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "version_practice.start",
            command_name=_COMMAND_NAME,
            practice_id=str(command.practice_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "version_practice.denied",
                command_name=_COMMAND_NAME,
                practice_id=str(command.practice_id),
                version_tag=command.version_tag,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.practice_id,
        )
        history: list[PracticeEvent] = [from_stored(s) for s in stored]
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
            stream_id=command.practice_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "version_practice.success",
            command_name=_COMMAND_NAME,
            practice_id=str(command.practice_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
