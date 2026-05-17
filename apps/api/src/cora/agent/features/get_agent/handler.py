"""Application handler for the `get_agent` query slice.

Cross-BC query-handler shape (Phase 2b precedent):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_agent(...)                -> Agent | None  (fold-on-read)
    3. return state                   -> caller maps None to 404 / isError

Returns the domain `Agent`, not a DTO. The route layer maps to
`AgentResponse` and the MCP tool maps to its own structured output.
"""

from typing import Protocol
from uuid import UUID

from cora.agent.aggregates.agent import Agent, load_agent
from cora.agent.errors import UnauthorizedError
from cora.agent.features.get_agent.query import GetAgent
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_QUERY_NAME = "GetAgent"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_agent handler implements."""

    async def __call__(
        self,
        query: GetAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Agent | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_agent handler closed over the shared deps."""

    async def handler(
        query: GetAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Agent | None:
        _log.info(
            "get_agent.start",
            query_name=_QUERY_NAME,
            agent_id=str(query.agent_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
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

        _log.info(
            "get_agent.success",
            query_name=_QUERY_NAME,
            agent_id=str(query.agent_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=agent is not None,
        )
        return agent

    return handler
