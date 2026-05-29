"""Application handler for the `release_control_of_surface` slice.

Longhand because the decider takes a `ReleaseControlOfSurfaceContext`
preloaded from the projection pool.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.visit import (
    VisitEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.trust.errors import UnauthorizedError
from cora.trust.features.release_control_of_surface.command import ReleaseControlOfSurface
from cora.trust.features.release_control_of_surface.context import (
    ReleaseControlOfSurfaceContext,
)
from cora.trust.features.release_control_of_surface.decider import decide
from cora.trust.projections.surface_active_visit import load_surface_active_visit

_STREAM_TYPE = "Visit"
_COMMAND_NAME = "ReleaseControlOfSurface"
_LOG_PREFIX = "release_control_of_surface"

_log = get_logger(_LOG_PREFIX)


class Handler(Protocol):
    """Callable interface every release_control_of_surface handler implements."""

    async def __call__(
        self,
        command: ReleaseControlOfSurface,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a release_control_of_surface handler closed over the shared deps."""

    async def handler(
        command: ReleaseControlOfSurface,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        visit_id = command.visit_id
        _log.info(
            f"{_LOG_PREFIX}.start",
            command_name=_COMMAND_NAME,
            visit_id=str(visit_id),
            surface_id=str(command.surface_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=command.surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                f"{_LOG_PREFIX}.denied",
                command_name=_COMMAND_NAME,
                visit_id=str(visit_id),
                surface_id=str(command.surface_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=visit_id,
        )
        history: list[VisitEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        active_holder = (
            await load_surface_active_visit(deps.pool, command.surface_id)
            if deps.pool is not None
            else None
        )
        context = ReleaseControlOfSurfaceContext(active_holder=active_holder)

        domain_events = decide(state=state, command=command, context=context, now=now)

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
            stream_id=visit_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            f"{_LOG_PREFIX}.success",
            command_name=_COMMAND_NAME,
            visit_id=str(visit_id),
            surface_id=str(command.surface_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
