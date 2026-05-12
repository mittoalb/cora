"""Application handler for the `version_method` slice.

Update-style handler shape — load + fold + decide + append. Not
idempotency-wrapped (re-versioning with the same tag is allowed by
design — see decider docstring).

**Stays longhand**: the command carries `version_tag` in addition
to `method_id`, and the handler logs it for diagnostic visibility.
Same justification as `version_capability` (Equipment 5f-2). Recipe
has only one Method transition that's purely method_id-only
(deprecate); a `make_method_update_handler` factory is parked at 1
single-field instance.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.method import (
    MethodEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.version_method.command import VersionMethod
from cora.recipe.features.version_method.decider import decide

_STREAM_TYPE = "Method"
_COMMAND_NAME = "VersionMethod"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every version_method handler implements."""

    async def __call__(
        self,
        command: VersionMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a version_method handler closed over the shared deps."""

    async def handler(
        command: VersionMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "version_method.start",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
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
                "version_method.denied",
                command_name=_COMMAND_NAME,
                method_id=str(command.method_id),
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
            stream_id=command.method_id,
        )
        history: list[MethodEvent] = [from_stored(s) for s in stored]
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
            stream_id=command.method_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "version_method.success",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
