"""Application handler for the `grant_tool_to_agent` slice.

Phase 8f-c iter 2. Built on the hoisted `make_agent_update_handler`
factory.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.grant_tool_to_agent.command import GrantToolToAgent
from cora.agent.features.grant_tool_to_agent.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every grant_tool_to_agent handler implements."""

    async def __call__(
        self,
        command: GrantToolToAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a grant_tool_to_agent handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="GrantToolToAgent",
        log_prefix="grant_tool_to_agent",
        decide_fn=decide,
    )
