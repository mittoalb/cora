"""Application handler for the `define_zone` slice.

Glues the pure decider to the infrastructure ports (Authorize, Clock,
IdGenerator, EventStore). Mirrors `register_actor.handler` shape — the
locked cross-BC create-style command pattern. Module-as-namespace:
callers use `from cora.trust.features import define_zone` then
`define_zone.bind(deps)` returning a `define_zone.Handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.trust.aggregates.zone import to_new_event
from cora.trust.errors import UnauthorizedError
from cora.trust.features.define_zone.command import DefineZone
from cora.trust.features.define_zone.decider import decide

_STREAM_TYPE = "Zone"
_COMMAND_NAME = "DefineZone"
_CONDUIT_DEFAULT = "default"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_zone handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator (in `cora.infrastructure.idempotency`) wraps a bare
    Handler into an `IdempotentHandler`; production wiring in
    `wire.py` always wraps. Tests use bare Handler when they don't
    need idempotency semantics.

    `causation_id` is the id of the event/message that triggered this
    command (None for HTTP / MCP root calls; sagas / process managers
    pass the upstream event's id).
    """

    async def __call__(
        self,
        command: DefineZone,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_zone handler with Idempotency-Key support.

    Same shape as `Handler` plus an optional `idempotency_key` kwarg.
    The wrapped form lives on `app.state.trust.define_zone` in
    production; routes pass through the inbound `Idempotency-Key`
    header.
    """

    async def __call__(
        self,
        command: DefineZone,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a define_zone handler closed over the shared deps."""

    async def handler(
        command: DefineZone,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID:
        _log.info(
            "define_zone.start",
            command_name=_COMMAND_NAME,
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
                "define_zone.denied",
                command_name=_COMMAND_NAME,
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
                event,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
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
            "define_zone.success",
            command_name=_COMMAND_NAME,
            zone_id=str(new_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
