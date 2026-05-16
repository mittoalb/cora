"""Application handler for the `register_decision` slice.

Three-step pre-load (Actor → optional parent Decision → decider).
Mirrors `register_dataset` precedent: cross-aggregate refs are
loaded for existence-only validation, bundled into a context VO,
handed to the pure decider.

## Cross-track surface

  - Actor (Access BC) is always loaded.
  - Parent Decision (own BC, recursive) is loaded when set.

Other BCs do NOT participate in the load. The optional `decision_inputs`
field can carry IDs from any BC (Run, Dataset, Subject, etc.) but
they are stored as opaque dict values; verifying them is a
projection / saga concern.
"""

from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import load_actor
from cora.decision.aggregates.decision import (
    DeciderActorMissingError,
    ParentDecisionMissingError,
    event_type_name,
    load_decision,
    to_payload,
)
from cora.decision.errors import UnauthorizedError
from cora.decision.features.register_decision.command import RegisterDecision
from cora.decision.features.register_decision.context import DecisionRegistrationContext
from cora.decision.features.register_decision.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RegisterDecision"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_decision handler, what `bind()` returns."""

    async def __call__(
        self,
        command: RegisterDecision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_decision handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterDecision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_decision handler closed over the shared deps."""

    async def handler(
        command: RegisterDecision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID:
        _log.info(
            "register_decision.start",
            command_name=_COMMAND_NAME,
            actor_id=str(command.actor_id),
            context=command.context,
            parent_id=str(command.parent_id) if command.parent_id is not None else None,
            override_kind=command.override_kind,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision_authz = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision_authz, Deny):
            _log.info(
                "register_decision.denied",
                command_name=_COMMAND_NAME,
                actor_id=str(command.actor_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision_authz.reason,
            )
            raise UnauthorizedError(decision_authz.reason)

        # Pre-load Actor (always; required field).
        actor = await load_actor(deps.event_store, command.actor_id)
        if actor is None:
            raise DeciderActorMissingError(command.actor_id)

        # Pre-load parent Decision (when ref set).
        parent = None
        if command.parent_id is not None:
            parent = await load_decision(deps.event_store, command.parent_id)
            if parent is None:
                raise ParentDecisionMissingError(command.parent_id)

        context = DecisionRegistrationContext(actor=actor, parent=parent)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
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
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_decision.success",
            command_name=_COMMAND_NAME,
            decision_id=str(new_id),
            actor_id=str(command.actor_id),
            context=command.context,
            parent_id=str(command.parent_id) if command.parent_id is not None else None,
            override_kind=command.override_kind,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
