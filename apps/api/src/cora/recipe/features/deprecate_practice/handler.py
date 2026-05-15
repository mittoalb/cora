"""Application handler for the `deprecate_practice` slice.

Update-style handler. Canonical body lives in
`cora.recipe._practice_update_handler.make_practice_update_handler`;
this module is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.recipe._practice_update_handler import make_practice_update_handler
from cora.recipe.features.deprecate_practice.command import DeprecatePractice
from cora.recipe.features.deprecate_practice.decider import decide


class Handler(Protocol):
    """Callable interface every deprecate_practice handler implements."""

    async def __call__(
        self,
        command: DeprecatePractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_practice handler closed over the shared deps."""
    return make_practice_update_handler(
        deps,
        command_name="DeprecatePractice",
        log_prefix="deprecate_practice",
        decide_fn=decide,
    )
