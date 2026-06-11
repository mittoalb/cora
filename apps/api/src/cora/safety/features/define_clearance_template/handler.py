"""Application handler for the `define_clearance_template` slice.

Same shape as `register_supply` (Slice 7A) and `register_asset` (Slice 8A)
handler: authz check, facility lookup via cross-BC port, decider call,
event append. Module-as-namespace: callers use
`from cora.safety.features import define_clearance_template` then
`define_clearance_template.bind(deps)` returning a
`define_clearance_template.Handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateCode,
    event_type_name,
    to_payload,
)
from cora.safety.aggregates.clearance_template._stream_id import (
    clearance_template_stream_id,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.define_clearance_template.command import (
    DefineClearanceTemplate,
)
from cora.safety.features.define_clearance_template.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_STREAM_TYPE = "ClearanceTemplate"
_COMMAND_NAME = "DefineClearanceTemplate"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_clearance_template handler  --  what `bind()` returns.

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
        command: DefineClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_clearance_template handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_clearance_template handler closed over the shared deps."""

    async def handler(
        command: DefineClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_clearance_template.start",
            command_name=_COMMAND_NAME,
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
                "define_clearance_template.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        facility_lookup_result = await deps.facility_lookup.lookup_by_code(
            FacilityCode(command.facility_code)
        )

        trimmed_code = ClearanceTemplateCode(command.code)
        stream_id = clearance_template_stream_id(
            command.facility_code,
            trimmed_code.value,
        )
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=stream_id,
            defined_by=ActorId(principal_id),
            facility_lookup_result=facility_lookup_result,
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
            stream_id=stream_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "define_clearance_template.success",
            command_name=_COMMAND_NAME,
            template_id=str(stream_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return stream_id

    return handler
