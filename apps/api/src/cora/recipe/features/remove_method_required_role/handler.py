"""Application handler for the `remove_method_required_role` slice.

Update-style handler. Mirror of `add_method_required_role.handler`:
the canonical body lives in `make_method_update_handler` and this
module is a thin slice-specific bind.

Not idempotency-wrapped: required-role mutation is strict-not-
idempotent at the decider (a second remove hits
`MethodRoleNameNotFoundError`).
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe._method_update_handler import make_method_update_handler
from cora.recipe.features.remove_method_required_role.command import (
    RemoveMethodRequiredRole,
)
from cora.recipe.features.remove_method_required_role.decider import decide


class Handler(Protocol):
    """Callable interface every remove_method_required_role handler implements."""

    async def __call__(
        self,
        command: RemoveMethodRequiredRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _extra_log_fields(command: RemoveMethodRequiredRole) -> dict[str, Any]:
    return {"role_name": command.role_name.value}


def bind(deps: Kernel) -> Handler:
    """Build a remove_method_required_role handler closed over the shared deps."""
    return make_method_update_handler(
        deps,
        command_name="RemoveMethodRequiredRole",
        log_prefix="remove_method_required_role",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )
