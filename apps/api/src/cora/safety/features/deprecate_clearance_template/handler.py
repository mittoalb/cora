"""Application handler for the `deprecate_clearance_template` slice.

LONGHAND inline-bind handler (not factory-based) because the decider
takes a `deprecated_by` kwarg that the cross-BC update factory does
not thread. Transition-only: loads the ClearanceTemplate aggregate,
delegates the Active -> Deprecated gate to the decider, and appends
the emitted `ClearanceTemplateDeprecated` event under optimistic
concurrency. No idempotency wrapping; transition slices are not
Idempotency-Key wrapped.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance_template import (
    event_type_name,
    from_stored,
    to_payload,
)
from cora.safety.aggregates.clearance_template.evolver import fold
from cora.safety.errors import UnauthorizedError
from cora.safety.features.deprecate_clearance_template.command import (
    DeprecateClearanceTemplate,
)
from cora.safety.features.deprecate_clearance_template.decider import decide
from cora.shared.identity import ActorId

_STREAM_TYPE = "ClearanceTemplate"
_COMMAND_NAME = "DeprecateClearanceTemplate"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every deprecate_clearance_template handler implements."""

    async def __call__(
        self,
        command: DeprecateClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_clearance_template handler closed over the shared deps."""

    async def handler(
        command: DeprecateClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "deprecate_clearance_template.start",
            command_name=_COMMAND_NAME,
            template_id=str(command.template_id),
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
                "deprecate_clearance_template.denied",
                command_name=_COMMAND_NAME,
                template_id=str(command.template_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.template_id)
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            deprecated_by=ActorId(principal_id),
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
            stream_id=command.template_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "deprecate_clearance_template.success",
            command_name=_COMMAND_NAME,
            template_id=str(command.template_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return None

    return handler
