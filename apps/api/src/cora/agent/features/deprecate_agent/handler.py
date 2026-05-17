"""Application handler for the `deprecate_agent` slice.

Update-style handler. Single-stream append. Not idempotency-wrapped:
transition handlers use the strict-not-idempotent guard at the
decider (re-deprecating an already-Deprecated agent raises
`AgentCannotDeprecateError` -> HTTP 409); HTTP-layer caching adds
no value for transitions.
"""

from typing import Protocol
from uuid import UUID

from cora.agent.aggregates.agent import (
    AgentNotFoundError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.agent.aggregates.agent.evolver import fold
from cora.agent.errors import UnauthorizedError
from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_STREAM_TYPE = "Agent"
_COMMAND_NAME = "DeprecateAgent"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every deprecate_agent handler implements."""

    async def __call__(
        self,
        command: DeprecateAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_agent handler closed over the shared deps."""

    async def handler(
        command: DeprecateAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "deprecate_agent.start",
            command_name=_COMMAND_NAME,
            agent_id=str(command.agent_id),
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
                "deprecate_agent.denied",
                command_name=_COMMAND_NAME,
                agent_id=str(command.agent_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.agent_id)
        if version == 0:
            raise AgentNotFoundError(command.agent_id)
        events = [from_stored(s) for s in stored]
        state = fold(events)
        if state is None:  # pragma: no cover  # version > 0 implies state non-None
            raise AgentNotFoundError(command.agent_id)

        now = deps.clock.now()
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
            stream_id=command.agent_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "deprecate_agent.success",
            command_name=_COMMAND_NAME,
            agent_id=str(command.agent_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
