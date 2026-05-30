"""Application handler for the `start_seal_republishing` slice.

Longhand update handler (mirrors `start_credential_rotation`): the
decider needs handler-injected `started_by_actor_id` to stamp the
audit denorm onto `SealRepublishingStarted`, so this slice cannot use
the `make_update_handler` factory. The longhand body wraps the same
load-authorize-fold-decide-append sequence.

The Seal stream UUID is deterministic per facility: the handler mints
it via UUID5 with the federation namespace per the singleton
convention locked on `cora.federation.aggregates.seal.state`. The
namespace constant is module-private; sibling Seal slices each derive
their stream id the same way.

Not idempotency-wrapped at wire.py: start_seal_republishing is a
strict-not-idempotent transition (starting against an already
Republishing Seal raises `SealCannotStartRepublishingError` -> HTTP
409); HTTP-layer caching adds no value when the decider rejects
replays.

Single-stream append; no cross-BC writes. Republishing start is not
itself a security-touching event (the online key is unchanged and the
offline root is the only signer during the window), so no
DecisionRegistered companion event is emitted. The cross-BC audit
shape lands on `rotate_seal_online_key` where the online key actually
changes.
"""

from typing import Protocol
from uuid import UUID, uuid5

from cora.federation.aggregates.seal import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.start_seal_republishing.command import (
    StartSealRepublishing,
)
from cora.federation.features.start_seal_republishing.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Seal"
_COMMAND_NAME = "StartSealRepublishing"
_FEDERATION_SEAL_NAMESPACE = UUID("01910000-0000-7000-8000-0000fede0001")

_log = get_logger(__name__)


def _seal_stream_id(facility_id: str) -> UUID:
    """Derive the singleton Seal stream UUID from facility_id."""
    return uuid5(_FEDERATION_SEAL_NAMESPACE, facility_id)


class Handler(Protocol):
    """Callable interface every start_seal_republishing handler implements."""

    async def __call__(
        self,
        command: StartSealRepublishing,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_seal_republishing handler closed over the shared deps."""

    async def handler(
        command: StartSealRepublishing,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "start_seal_republishing.start",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
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
                "start_seal_republishing.denied",
                command_name=_COMMAND_NAME,
                facility_id=command.facility_id,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stream_id = _seal_stream_id(command.facility_id)
        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=stream_id,
        )
        state = fold([from_stored(s) for s in stored])

        now = deps.clock.now()

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            started_by_actor_id=principal_id,
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
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "start_seal_republishing.success",
            command_name=_COMMAND_NAME,
            facility_id=command.facility_id,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
