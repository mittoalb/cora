"""Application handler for the `suspend_agent` slice.

Built on the actor-stamping `make_agent_actor_update_handler`
factory variant: the envelope's `principal_id` threads into the
decider under `suspended_by`, landing on `AgentSuspended.suspended_by`
and the Agent aggregate's `suspended_by` state field per
[[project_fold_symmetry_design]].
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_actor_update_handler
from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every suspend_agent handler implements."""

    async def __call__(
        self,
        command: SuspendAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a suspend_agent handler closed over the shared deps."""
    return make_agent_actor_update_handler(
        deps,
        command_name="SuspendAgent",
        log_prefix="suspend_agent",
        decide_fn=decide,
        actor_kwarg="suspended_by",
    )
