"""Application handler for the `resume_agent` slice.

Phase 8f-c iter 2. Built on the hoisted `make_agent_update_handler`
factory.
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.resume_agent.command import ResumeAgent
from cora.agent.features.resume_agent.decider import decide
from cora.infrastructure.kernel import Kernel


class Handler(Protocol):
    """Callable interface every resume_agent handler implements."""

    async def __call__(
        self,
        command: ResumeAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a resume_agent handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="ResumeAgent",
        log_prefix="resume_agent",
        decide_fn=decide,
    )
