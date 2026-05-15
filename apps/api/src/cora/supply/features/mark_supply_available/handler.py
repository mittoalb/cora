"""Application handler for the `mark_supply_available` slice.

Update-style handler shape: load + authorize + fold + decide +
append. Longhand body for 10a-a; the per-aggregate factory hoist
(`make_supply_update_handler`) lands at 10a-b when 4 more transition
slices arrive (rule-of-three precedent: Asset's
`_asset_update_handler` was hoisted at 5e after 4 instances).

Not idempotency-wrapped: transition handlers use the
strict-not-idempotent guard at the decider (re-marking an already-
Available supply raises `SupplyCannotMarkAvailableError` -> HTTP
409); HTTP-layer caching adds no value for transitions.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.supply.aggregates.supply import (
    SupplyEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable
from cora.supply.features.mark_supply_available.decider import decide

_STREAM_TYPE = "Supply"
_COMMAND_NAME = "MarkSupplyAvailable"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every mark_supply_available handler implements."""

    async def __call__(
        self,
        command: MarkSupplyAvailable,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a mark_supply_available handler closed over the shared deps."""

    async def handler(
        command: MarkSupplyAvailable,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "mark_supply_available.start",
            command_name=_COMMAND_NAME,
            supply_id=str(command.supply_id),
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
                "mark_supply_available.denied",
                command_name=_COMMAND_NAME,
                supply_id=str(command.supply_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.supply_id,
        )
        history: list[SupplyEvent] = [from_stored(s) for s in stored]
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
            stream_id=command.supply_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "mark_supply_available.success",
            command_name=_COMMAND_NAME,
            supply_id=str(command.supply_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
