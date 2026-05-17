"""Application handler for the `revoke_tool_from_agent` slice.

Phase 8f-c iter 2. Built on the hoisted `make_agent_update_handler`
factory.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.revoke_tool_from_agent.command import RevokeToolFromAgent
from cora.agent.features.revoke_tool_from_agent.decider import decide
from cora.infrastructure.kernel import Kernel


class Handler(Protocol):
    """Callable interface every revoke_tool_from_agent handler implements."""

    async def __call__(
        self,
        command: RevokeToolFromAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a revoke_tool_from_agent handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="RevokeToolFromAgent",
        log_prefix="revoke_tool_from_agent",
        decide_fn=decide,
    )
