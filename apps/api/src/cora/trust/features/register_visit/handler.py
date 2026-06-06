"""Application handler for the `register_visit` slice.

Genesis-style handler (longhand). Mirrors `define_policy.handler`
shape exactly: bare `Handler` Protocol, idempotency-wrapped
`IdempotentHandler` Protocol, `bind(deps)` factory.

Caller-supplied `visit_id` means the handler does NOT call
`deps.id_generator.new_id()` for the visit's id. It still uses the
generator for the per-event `event_id`.

`expected_version=0` per genesis pattern: the stream MUST be empty;
optimistic-concurrency guarantee surfaces collision as
`VisitAlreadyExistsError` (decider) OR `ConcurrencyError` (event-
store).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.visit import event_type_name, load_visit, to_payload
from cora.trust.errors import UnauthorizedError
from cora.trust.features.register_visit.command import RegisterVisit
from cora.trust.features.register_visit.context import RegisterVisitContext
from cora.trust.features.register_visit.decider import decide

_STREAM_TYPE = "Visit"
_COMMAND_NAME = "RegisterVisit"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_visit handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: RegisterVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_visit handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_visit handler closed over the shared deps."""

    async def handler(
        command: RegisterVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_visit.start",
            command_name=_COMMAND_NAME,
            visit_id=str(command.visit_id),
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
                "register_visit.denied",
                command_name=_COMMAND_NAME,
                visit_id=str(command.visit_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        parent_visit = (
            await load_visit(deps.event_store, command.parent_id)
            if command.parent_id is not None
            else None
        )
        context = RegisterVisitContext(parent_visit=parent_visit)

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
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
            stream_id=command.visit_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_visit.success",
            command_name=_COMMAND_NAME,
            visit_id=str(command.visit_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return command.visit_id

    return handler
