"""Application handler for the `revise_agent_budget` slice.

Phase 8f-c iter 2. Built on the hoisted `make_agent_update_handler`
factory.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.revise_agent_budget.command import ReviseAgentBudget
from cora.agent.features.revise_agent_budget.decider import decide
from cora.infrastructure.kernel import Kernel


class Handler(Protocol):
    """Callable interface every revise_agent_budget handler implements."""

    async def __call__(
        self,
        command: ReviseAgentBudget,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a revise_agent_budget handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="ReviseAgentBudget",
        log_prefix="revise_agent_budget",
        decide_fn=decide,
    )
