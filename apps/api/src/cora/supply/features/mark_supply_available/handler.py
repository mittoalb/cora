"""Application handler for the `mark_supply_available` slice.

Update-style handler. The full canonical body lives in
`cora.supply._supply_update_handler.make_supply_update_handler`
(load + authorize + fold + decide + append, with structured logging
at each boundary). This module is a thin slice-specific bind.

Not idempotency-wrapped: transition handlers use the
strict-not-idempotent guard at the decider (re-marking an already-
Available supply raises `SupplyCannotMarkAvailableError` -> HTTP
409); HTTP-layer caching adds no value for transitions.

## Factory hoist (10a-b)

10a-a shipped this handler longhand because rule-of-three hadn't
fired (only one update-style handler then). 10a-b adds 4 more
transition slices; the factory at `_supply_update_handler.py`
landed alongside and this slice was refactored to use it. Mirrors
Asset's degrade/fault/restore slices using
`make_asset_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.supply._supply_update_handler import make_supply_update_handler
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable
from cora.supply.features.mark_supply_available.decider import decide


class Handler(Protocol):
    """Callable interface every mark_supply_available handler implements."""

    async def __call__(
        self,
        command: MarkSupplyAvailable,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a mark_supply_available handler closed over the shared deps."""
    return make_supply_update_handler(
        deps,
        command_name="MarkSupplyAvailable",
        log_prefix="mark_supply_available",
        decide_fn=decide,
    )
