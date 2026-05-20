"""Application handler for the `remove_plan_wire` slice (Phase 6h).

Update-style handler: load + fold + decide + append. Loads ONLY the
Plan stream (no Asset loads needed; removal doesn't need cross-
aggregate context). Stays longhand for symmetry with the rest of
the Recipe BC's update-style handlers.

NOT idempotency-wrapped: wire-mutation is strict-not-idempotent at
the decider (re-remove raises `PlanWireNotFoundError`).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.remove_plan_wire.command import RemovePlanWire
from cora.recipe.features.remove_plan_wire.decider import decide

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "RemovePlanWire"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every remove_plan_wire handler implements."""

    async def __call__(
        self,
        command: RemovePlanWire,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a remove_plan_wire handler closed over the shared deps."""

    async def handler(
        command: RemovePlanWire,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "remove_plan_wire.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            source_asset_id=str(command.source_asset_id),
            target_asset_id=str(command.target_asset_id),
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
                "remove_plan_wire.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.plan_id,
        )
        history: list[PlanEvent] = [from_stored(s) for s in stored]
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
            stream_id=command.plan_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "remove_plan_wire.success",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            source_asset_id=str(command.source_asset_id),
            target_asset_id=str(command.target_asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
