"""Application handler for the `detach_asset_from_fixture` slice.

Update-style handler. Loads the Asset stream (gives us current_version
for the append), calls the pure decider, appends. The Fixture is NOT
loaded: detach only mutates the Asset side.

Update-style (not idempotency-wrapped): retries are domain-idempotent
via AssetNotAttachedToFixtureError on the second call.
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
from cora.equipment.features.detach_asset_from_fixture.command import DetachAssetFromFixture
from cora.equipment.features.detach_asset_from_fixture.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "DetachAssetFromFixture"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every detach_asset_from_fixture handler implements."""

    async def __call__(
        self,
        command: DetachAssetFromFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a detach_asset_from_fixture handler closed over the shared deps."""

    async def handler(
        command: DetachAssetFromFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "detach_asset_from_fixture.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            fixture_id=str(command.fixture_id),
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
                "detach_asset_from_fixture.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
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
                principal_id=principal_id,
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
            "detach_asset_from_fixture.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            fixture_id=str(command.fixture_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
