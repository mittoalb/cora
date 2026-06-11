"""Application handler for the `remove_dataset_from_edition` slice.

Update-style; no Dataset peer load (set-removal is well-defined
regardless of the Dataset's current status).
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.edition import (
    EditionEvent,
    EditionNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.remove_dataset_from_edition.command import (
    RemoveDatasetFromEdition,
)
from cora.data.features.remove_dataset_from_edition.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Edition"
_COMMAND_NAME = "RemoveDatasetFromEdition"

_log = get_logger(__name__)


class Handler(Protocol):
    async def __call__(
        self,
        command: RemoveDatasetFromEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a remove_dataset_from_edition handler closed over the shared deps."""

    async def handler(
        command: RemoveDatasetFromEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "remove_dataset_from_edition.start",
            command_name=_COMMAND_NAME,
            edition_id=str(command.edition_id),
            dataset_id=str(command.dataset_id),
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
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.edition_id,
        )
        history: list[EditionEvent] = [from_stored(s) for s in stored]
        state = fold(history)
        if state is None:
            raise EditionNotFoundError(command.edition_id)

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            removed_by=ActorId(principal_id),
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
            stream_id=command.edition_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "remove_dataset_from_edition.success",
            command_name=_COMMAND_NAME,
            edition_id=str(command.edition_id),
            dataset_id=str(command.dataset_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
