"""Application handler for the `deprecate_agent` slice.

Phase 8f-c iter 2: migrated to the hoisted
`make_agent_update_handler` factory. Zero behavior change.

Phase 8f-c iter 2 also expanded the source set: `Suspended` is now
a valid source state for deprecation (the decider's guard is what
enforces this; the handler factory is source-set-agnostic).
"""

from typing import Protocol
from uuid import UUID

from cora.agent._agent_update_handler import make_agent_update_handler
from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every deprecate_agent handler implements."""

    async def __call__(
        self,
        command: DeprecateAgent,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_agent handler closed over the shared deps."""
    return make_agent_update_handler(
        deps,
        command_name="DeprecateAgent",
        log_prefix="deprecate_agent",
        decide_fn=decide,
    )
