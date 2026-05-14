"""Application handler for the `update_method_parameters_schema` slice.

Phase 6g-a. Update-style: load + fold + decide + append. Not
idempotency-wrapped (no-op-on-unchanged is handled at the decider
layer; cross-process replay safety is the IdempotencyStore concern,
not in scope for an update slice). Mirrors
`update_capability_schema` (Equipment 5g-a) handler shape.
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
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema.decider import decide

_STREAM_TYPE = "Method"
_COMMAND_NAME = "UpdateMethodParametersSchema"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_method_parameters_schema handler implements."""

    async def __call__(
        self,
        command: UpdateMethodParametersSchema,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_method_parameters_schema handler closed over the shared deps."""

    async def handler(
        command: UpdateMethodParametersSchema,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "update_method_parameters_schema.start",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
            schema_present=command.parameters_schema is not None,
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
                "update_method_parameters_schema.denied",
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

        if not domain_events:
            _log.info(
                "update_method_parameters_schema.no_op",
                command_name=_COMMAND_NAME,
                method_id=str(command.method_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
            )
            return

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
            "update_method_parameters_schema.success",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
            schema_present=command.parameters_schema is not None,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
