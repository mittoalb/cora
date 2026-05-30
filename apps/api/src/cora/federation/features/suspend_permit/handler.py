"""Application handler for the `suspend_permit` slice.

Update-style handler (loads the Permit aggregate, validates the FSM
transition, appends a `PermitSuspended` event). NOT idempotency-
wrapped: transition handlers rely on the strict-not-idempotent guard
at the decider (re-suspending an already-Suspended permit raises
`PermitCannotSuspendError` -> HTTP 409); HTTP-layer caching adds no
value for transitions.

## Why longhand (no `_permit_update_handler` factory call)

`PermitSuspended` carries `suspended_by_actor_id` on its payload
(audit anchor for the operator gesture). The shared
`make_update_handler` factory only threads `state`, `command`, and
`now` into the decider, so it cannot pass `principal_id`. Mirrors the
Calibration `append_revision` precedent (decider needs
`established_by_actor_id`, so the handler stays longhand). When all
four Permit transition slices have shipped longhand, a Permit-
flavored factory variant that threads `<verb>_by_actor_id` may
emerge at rule-of-three.
"""

from typing import Protocol
from uuid import UUID

from cora.federation.aggregates.permit import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.suspend_permit.command import SuspendPermit
from cora.federation.features.suspend_permit.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Permit"
_COMMAND_NAME = "SuspendPermit"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every suspend_permit handler implements."""

    async def __call__(
        self,
        command: SuspendPermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a suspend_permit handler closed over the shared deps."""

    async def handler(
        command: SuspendPermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "suspend_permit.start",
            command_name=_COMMAND_NAME,
            permit_id=str(command.permit_id),
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
                "suspend_permit.denied",
                command_name=_COMMAND_NAME,
                permit_id=str(command.permit_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.permit_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()
        domain_events = decide(
            state=state,
            command=command,
            now=now,
            suspended_by_actor_id=principal_id,
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
            stream_id=command.permit_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "suspend_permit.success",
            command_name=_COMMAND_NAME,
            permit_id=str(command.permit_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
