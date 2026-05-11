"""Application handler for the `deprecate_capability` slice.

Update-style handler — single-field command (just capability_id).
**Stays longhand** for now; a `make_capability_update_handler`
factory is parked at 1 instance (deprecate is the only single-field
Capability transition; version takes a version_tag and stays
longhand for log-field reasons). Revisit factory extraction at 3+
single-field Capability transitions if Capability ever grows further
update-style slices.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.capability import (
    CapabilityEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.deprecate_capability.command import DeprecateCapability
from cora.equipment.features.deprecate_capability.decider import decide
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_STREAM_TYPE = "Capability"
_COMMAND_NAME = "DeprecateCapability"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every deprecate_capability handler implements."""

    async def __call__(
        self,
        command: DeprecateCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a deprecate_capability handler closed over the shared deps."""

    async def handler(
        command: DeprecateCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "deprecate_capability.start",
            command_name=_COMMAND_NAME,
            capability_id=str(command.capability_id),
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
                "deprecate_capability.denied",
                command_name=_COMMAND_NAME,
                capability_id=str(command.capability_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.capability_id,
        )
        history: list[CapabilityEvent] = [from_stored(s) for s in stored]
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
            stream_id=command.capability_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "deprecate_capability.success",
            command_name=_COMMAND_NAME,
            capability_id=str(command.capability_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
