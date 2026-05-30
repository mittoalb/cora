"""Application handler for the `revoke_permit` slice.

Longhand update handler (mirrors `append_revision`): the decider
needs handler-injected `revoked_by_actor_id` to stamp the audit
denorm onto `PermitRevoked`, so this slice cannot use the
`make_update_handler` factory (which only forwards `state`,
`command`, `now`). The longhand body wraps the same load-authorize-
fold-decide-append sequence.

Not idempotency-wrapped at wire.py: revoke is a strict-not-idempotent
transition (re-revoking raises `PermitCannotRevokeError` -> HTTP 409);
HTTP-layer caching adds no value when the decider rejects replays.
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
from cora.federation.features.revoke_permit.command import RevokePermit
from cora.federation.features.revoke_permit.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Permit"
_COMMAND_NAME = "RevokePermit"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every revoke_permit handler implements."""

    async def __call__(
        self,
        command: RevokePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a revoke_permit handler closed over the shared deps."""

    async def handler(
        command: RevokePermit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "revoke_permit.start",
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
                "revoke_permit.denied",
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
            revoked_by_actor_id=principal_id,
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
            "revoke_permit.success",
            command_name=_COMMAND_NAME,
            permit_id=str(command.permit_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
