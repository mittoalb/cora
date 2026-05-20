"""Application handler for the `register_procedure` slice.

Same shape as `register_supply` / `register_actor` / `register_subject`
/ `define_zone` / `define_conduit` / `define_policy` /
`define_family` / `register_asset` / `define_method` -- the
locked cross-BC create-style command pattern.

Module-as-namespace: callers use
`from cora.operation.features import register_procedure` then
`register_procedure.bind(deps)` returning a
`register_procedure.Handler`.

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls; sagas / process managers
pass the upstream event's id).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.aggregates.procedure import event_type_name, to_payload
from cora.operation.errors import UnauthorizedError
from cora.operation.features.register_procedure.command import RegisterProcedure
from cora.operation.features.register_procedure.decider import decide
from cora.recipe.aggregates.capability import load_capability

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "RegisterProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_procedure handler -- what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.
    """

    async def __call__(
        self,
        command: RegisterProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_procedure handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_procedure handler closed over the shared deps."""

    async def handler(
        command: RegisterProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_procedure.start",
            command_name=_COMMAND_NAME,
            kind=command.kind,
            target_asset_count=len(command.target_asset_ids),
            parent_run_id=str(command.parent_run_id) if command.parent_run_id is not None else None,
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
                "register_procedure.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        # Phase 10d-additive: load the bound Capability via cross-BC
        # port only when the command supplied one. None passes through
        # to the decider; when capability_id is set but the stream
        # doesn't exist, decider raises CapabilityNotFoundError.
        capability = (
            await load_capability(deps.event_store, command.capability_id)
            if command.capability_id is not None
            else None
        )

        domain_events = decide(
            state=None,
            command=command,
            capability=capability,
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
            "register_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
