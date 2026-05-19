"""Application handler for the `version_family` slice.

Update-style handler shape — load + fold + decide + append. Not
idempotency-wrapped (domain-idempotent: re-versioning with the same
tag is still a real revision the operator wanted; a future
optional-no-op semantics would need different framing).

**Stays longhand** (does not use any factory): the command carries
`version_tag` in addition to `family_id`, and the handler logs
it for diagnostic visibility. Same justification as relocate_asset
and add/remove_asset_family. Equipment has only one Family
transition that's purely family_id-only (deprecate); a
`make_capability_update_handler` factory is parked at 1 instance.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.family import (
    FamilyEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.version_family.command import VersionFamily
from cora.equipment.features.version_family.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Family"
_COMMAND_NAME = "VersionFamily"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every version_family handler implements."""

    async def __call__(
        self,
        command: VersionFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a version_family handler closed over the shared deps."""

    async def handler(
        command: VersionFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "version_family.start",
            command_name=_COMMAND_NAME,
            family_id=str(command.family_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "version_family.denied",
                command_name=_COMMAND_NAME,
                family_id=str(command.family_id),
                version_tag=command.version_tag,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.family_id,
        )
        history: list[FamilyEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(state=state, command=command, now=now)

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
            stream_id=command.family_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "version_family.success",
            command_name=_COMMAND_NAME,
            family_id=str(command.family_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
