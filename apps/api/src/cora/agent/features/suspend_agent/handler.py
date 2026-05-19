"""Application handler for the `suspend_agent` slice.

Phase 8f-c iter 2. Built on the hoisted `make_agent_update_handler`
factory (same shape as version_agent / deprecate_agent post-hoist).
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.decider import decide
from cora.infrastructure.kernel import Kernel

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every suspend_agent handler implements."""

    async def __call__(
        self,
        command: SuspendAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a suspend_agent handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="SuspendAgent",
        log_prefix="suspend_agent",
        decide_fn=decide,
    )
