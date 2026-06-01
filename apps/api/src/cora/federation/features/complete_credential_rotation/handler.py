"""Application handler for the `complete_credential_rotation` slice.

Longhand update handler (mirrors `revoke_permit` / `activate_permit` /
`append_calibration_revision`): the decider needs handler-injected
`rotation_completed_by_actor_id` to stamp the audit denorm onto
`CredentialRotationCompleted`, so this slice cannot use the
`make_update_handler` factory (which only forwards `state`, `command`,
`now`). The longhand body wraps the same load-authorize-fold-decide-
append sequence.

Not idempotency-wrapped at wire.py: completing a rotation is strict-
not-idempotent at the decider (completing on a non-Rotating credential
raises `CredentialCannotRotateError` -> HTTP 409); HTTP-layer caching
adds no value when the decider rejects replays.
"""

from typing import Protocol
from uuid import UUID

from cora.federation.aggregates.credential import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.complete_credential_rotation.command import (
    CompleteCredentialRotation,
)
from cora.federation.features.complete_credential_rotation.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Credential"
_COMMAND_NAME = "CompleteCredentialRotation"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every complete_credential_rotation handler implements."""

    async def __call__(
        self,
        command: CompleteCredentialRotation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a complete_credential_rotation handler closed over the shared deps."""

    async def handler(
        command: CompleteCredentialRotation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "complete_credential_rotation.start",
            command_name=_COMMAND_NAME,
            credential_id=str(command.credential_id),
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
                "complete_credential_rotation.denied",
                command_name=_COMMAND_NAME,
                credential_id=str(command.credential_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.credential_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            rotation_completed_by_actor_id=principal_id,
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
            stream_id=command.credential_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "complete_credential_rotation.success",
            command_name=_COMMAND_NAME,
            credential_id=str(command.credential_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
