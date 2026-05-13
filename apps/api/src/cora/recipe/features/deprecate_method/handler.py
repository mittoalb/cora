"""Application handler for the `deprecate_method` slice.

Update-style handler — single-field command (just method_id).
**Stays longhand** for now; a `make_method_update_handler` factory
is parked at 1 single-field instance (deprecate is the only single-
field Method transition; version takes a version_tag and stays
longhand for log-field reasons). Revisit factory extraction at 3+
single-field Method transitions.
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
from cora.recipe.features.deprecate_method.command import DeprecateMethod
from cora.recipe.features.deprecate_method.decider import decide

_STREAM_TYPE = "Method"
_COMMAND_NAME = "DeprecateMethod"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every deprecate_method handler implements."""

    async def __call__(
        self,
        command: DeprecateMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_method handler closed over the shared deps."""

    async def handler(
        command: DeprecateMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "deprecate_method.start",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
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
                "deprecate_method.denied",
                command_name=_COMMAND_NAME,
                method_id=str(command.method_id),
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
                principal_id=principal_id,
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
            "deprecate_method.success",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
