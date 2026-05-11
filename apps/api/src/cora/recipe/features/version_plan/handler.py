"""Application handler for the `version_plan` slice.

Update-style handler shape — load + fold + decide + append. Not
idempotency-wrapped (re-versioning with the same tag is allowed by
design — see decider docstring).

**Stays longhand**: command carries `version_tag` in addition to
`plan_id`, and the handler logs it for diagnostic visibility.
Same justification as version_practice / version_method /
version_capability.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.version_plan.command import VersionPlan
from cora.recipe.features.version_plan.decider import decide

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "VersionPlan"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every version_plan handler implements."""

    async def __call__(
        self,
        command: VersionPlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a version_plan handler closed over the shared deps."""

    async def handler(
        command: VersionPlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "version_plan.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            version_tag=command.version_tag,
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
                "version_plan.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
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
            "version_plan.success",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
