"""Application handler for the `unbind_plan_role` slice.

Single-stream update; uses the `make_plan_update_handler` factory
(unbind needs no cross-aggregate Method/Asset load).

NOT idempotency-wrapped: unbind is strict-not-idempotent at the
decider (`PlanRoleNotBoundError`).
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe._plan_update_handler import make_plan_update_handler
from cora.recipe.features.unbind_plan_role.command import UnbindPlanRole
from cora.recipe.features.unbind_plan_role.decider import decide


class Handler(Protocol):
    """Callable interface every unbind_plan_role handler implements."""

    async def __call__(
        self,
        command: UnbindPlanRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _extra_log_fields(command: UnbindPlanRole) -> dict[str, Any]:
    return {"role_name": command.role_name.value}


def bind(deps: Kernel) -> Handler:
    """Build an unbind_plan_role handler closed over the shared deps."""
    return make_plan_update_handler(
        deps,
        command_name="UnbindPlanRole",
        log_prefix="unbind_plan_role",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )
