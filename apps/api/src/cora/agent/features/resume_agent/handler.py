"""Application handler for the `resume_agent` slice.

Built on the actor-stamping `make_agent_actor_update_handler`
factory variant: the envelope's `principal_id` threads into the
decider under `resumed_by`, landing on `AgentResumed.resumed_by`
and the Agent aggregate's `resumed_by` state field per
[[project_fold_symmetry_design]].
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_actor_update_handler
from cora.agent.features.resume_agent.command import ResumeAgent
from cora.agent.features.resume_agent.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every resume_agent handler implements."""

    async def __call__(
        self,
        command: ResumeAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a resume_agent handler closed over the shared deps."""
    return make_agent_actor_update_handler(
        deps,
        command_name="ResumeAgent",
        log_prefix="resume_agent",
        decide_fn=decide,
        actor_kwarg="resumed_by",
    )
