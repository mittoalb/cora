"""Application handler for the `deprecate_method` slice.

Update-style handler. Canonical body lives in
`cora.recipe._method_update_handler.make_method_update_handler`;
this module is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.recipe._method_update_handler import make_method_update_handler
from cora.recipe.features.deprecate_method.command import DeprecateMethod
from cora.recipe.features.deprecate_method.decider import decide


class Handler(Protocol):
    """Callable interface every deprecate_method handler implements."""

    async def __call__(
        self,
        command: DeprecateMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_method handler closed over the shared deps."""
    return make_method_update_handler(
        deps,
        command_name="DeprecateMethod",
        log_prefix="deprecate_method",
        decide_fn=decide,
    )
