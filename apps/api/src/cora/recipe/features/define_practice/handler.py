"""Application handler for the `define_practice` slice.

Same shape as `define_method` / `define_family` / etc — the
locked cross-BC create-style command pattern. Module-as-namespace:
callers use `from cora.recipe.features import define_practice` then
`define_practice.bind(deps)` returning a `define_practice.Handler`.

Ninth instance of the create-style template body. Cross-BC
extraction question still parked (8 instances at 6a, 9 here);
threading 9 BCs through one factory is a bigger refactor than
threading the next instance through a per-BC helper.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.practice import event_type_name, to_payload
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.define_practice.command import DefinePractice
from cora.recipe.features.define_practice.decider import decide

_STREAM_TYPE = "Practice"
_COMMAND_NAME = "DefinePractice"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_practice handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.

    `causation_id` is the id of the event/message that triggered
    this command (None for HTTP / MCP root calls; sagas / process
    managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: DefinePractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_practice handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefinePractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_practice handler closed over the shared deps."""

    async def handler(
        command: DefinePractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> UUID:
        _log.info(
            "define_practice.start",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
            site_id=str(command.site_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "define_practice.denied",
                command_name=_COMMAND_NAME,
                method_id=str(command.method_id),
                site_id=str(command.site_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
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
            "define_practice.success",
            command_name=_COMMAND_NAME,
            practice_id=str(new_id),
            method_id=str(command.method_id),
            site_id=str(command.site_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
