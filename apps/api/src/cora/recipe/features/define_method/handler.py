"""Application handler for the `define_method` slice.

Same shape as `register_actor` / `register_subject` / `define_zone`
/ `define_conduit` / `define_policy` / `define_capability` /
`register_asset` — the locked cross-BC create-style command pattern.
Module-as-namespace: callers use
`from cora.recipe.features import define_method` then
`define_method.bind(deps)` returning a `define_method.Handler`.

Eighth instance of the create-style template body. The cross-BC
extraction question reopens periodically (parked since the
post-Phase-4 review at 5 instances; reviewed and re-deferred at 7
instances after 5b, 8 instances after 6a, 10 instances after 6e-1,
and 11 instances after 6f-1).

After 6f-1, two distinct create-style shapes coexist:
  - **Simple create** (no cross-aggregate loads) — 9 instances:
    register_actor, register_subject, define_zone, define_conduit,
    define_policy, define_capability, register_asset, define_method,
    define_practice.
  - **Cross-aggregate-validating create** (handler pre-loads + slice-
    local context dataclass) — 2 instances: define_plan
    (PlanBindingContext, 6e-1) and start_run (RunStartContext, 6f-1).

The two shapes have meaningfully different handler bodies; a
unifying factory across them would lose more than it saves.

Stance: keep the extraction question OPEN, not killed. The create-
style landscape is still evolving — future modes may surface (async-
bound creates, scheduled creates, multi-step transactional creates,
saga-driven creates, etc.) that change the calculus. Re-evaluate
when (a) two of the existing modes converge in shape over time,
(b) a third mode emerges that shares structure with one of the
existing two, or (c) cross-cutting decorators (logging, authz,
idempotency wrapping) consolidate enough to obviate handler-body
extraction. Until then, the duplication is cheaper to read than a
premature abstraction would be.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.method import event_type_name, to_payload
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.define_method.command import DefineMethod
from cora.recipe.features.define_method.decider import decide

_STREAM_TYPE = "Method"
_COMMAND_NAME = "DefineMethod"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_method handler — what `bind()` returns.

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
        command: DefineMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_method handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a define_method handler closed over the shared deps."""

    async def handler(
        command: DefineMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID:
        _log.info(
            "define_method.start",
            command_name=_COMMAND_NAME,
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
                "define_method.denied",
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
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "define_method.success",
            command_name=_COMMAND_NAME,
            method_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
