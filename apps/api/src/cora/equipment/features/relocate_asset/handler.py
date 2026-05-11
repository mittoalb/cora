"""Application handler for the `relocate_asset` slice.

Update-style handler shape — same template as `activate_asset` /
`decommission_asset`. Load + fold + decide + append. Not
idempotency-wrapped.

Per the 5c decision, Equipment defers per-BC update-handler
factory extraction to 5e (when 4-5 update-style handlers will
exist). 5d adds the third instance; 5e adds the fourth+. Each
handler body stays inlined for now.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.relocate_asset.command import RelocateAsset
from cora.equipment.features.relocate_asset.decider import decide
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "RelocateAsset"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every relocate_asset handler implements."""

    async def __call__(
        self,
        command: RelocateAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a relocate_asset handler closed over the shared deps."""

    async def handler(
        command: RelocateAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "relocate_asset.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            to_parent_id=str(command.to_parent_id),
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
                "relocate_asset.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
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
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "relocate_asset.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            to_parent_id=str(command.to_parent_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
