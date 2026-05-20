"""Application handler for the `get_agent` query slice.

Path C (audit-2026-05-20 Iter C-2): handler returns AgentView
bundling aggregate state + projection-sourced lifecycle timestamps.
State stays decider-minimal; lifecycle timestamps live on the
projection (`proj_agent_summary`, Iter C-1) per Dudycz read-side-
pragmatism + K8s/GitHub/AIP-142 resource-API precedent. Mirrors
the pattern from Iter A (Method) + Iter B-1/B-2/B-3/B-4
(Plan/Practice/Family/Capability).

Workflow:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_agent(...)                -> Agent | None  (fold-on-read)
    3. load_agent_timestamps(...)     -> AgentLifecycleTimestamps | None
                                         (None when projection lags or
                                          pool not configured)
    4. return AgentView               -> caller maps None to 404 / isError;
                                         maps view.timestamps fields onto
                                         the response DTO

Suspended/Resumed timestamps are NOT folded in here — they live on
aggregate state because `suspension_reason` is invariant-bearing.
The route DTO reads them from view.agent.suspended_at /
view.agent.resumed_at directly.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.agent.aggregates.agent import (
    Agent,
    AgentLifecycleTimestamps,
    load_agent,
    load_agent_timestamps,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features.get_agent.query import GetAgent
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetAgent"

_log = get_logger(__name__)


@dataclass(frozen=True)
class AgentView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not an Agent-not-found
    signal (use a None `AgentView` for that)."""

    agent: Agent
    timestamps: AgentLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_agent handler implements."""

    async def __call__(
        self,
        query: GetAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AgentView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_agent handler closed over the shared deps."""

    async def handler(
        query: GetAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AgentView | None:
        _log.info(
            "get_agent.start",
            query_name=_QUERY_NAME,
            agent_id=str(query.agent_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_agent.denied",
                query_name=_QUERY_NAME,
                agent_id=str(query.agent_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        agent = await load_agent(deps.event_store, query.agent_id)
        if agent is None:
            _log.info(
                "get_agent.success",
                query_name=_QUERY_NAME,
                agent_id=str(query.agent_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: AgentLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_agent_timestamps(deps.pool, query.agent_id)

        _log.info(
            "get_agent.success",
            query_name=_QUERY_NAME,
            agent_id=str(query.agent_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return AgentView(agent=agent, timestamps=timestamps)

    return handler
