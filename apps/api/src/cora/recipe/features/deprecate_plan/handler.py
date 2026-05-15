"""Application handler for the `deprecate_plan` slice.

Update-style handler. Canonical body lives in
`cora.recipe._plan_update_handler.make_plan_update_handler`;
this module is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.recipe._plan_update_handler import make_plan_update_handler
from cora.recipe.features.deprecate_plan.command import DeprecatePlan
from cora.recipe.features.deprecate_plan.decider import decide


class Handler(Protocol):
    """Callable interface every deprecate_plan handler implements."""

    async def __call__(
        self,
        command: DeprecatePlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_plan handler closed over the shared deps."""
    return make_plan_update_handler(
        deps,
        command_name="DeprecatePlan",
        log_prefix="deprecate_plan",
        decide_fn=decide,
    )
