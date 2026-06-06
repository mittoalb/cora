"""Application handler for the `add_method_required_role` slice.

Update-style handler. The canonical body lives in
`make_method_update_handler` (load + authorize + fold + decide +
append, with structured logging). This module is a thin slice-
specific bind.

Not idempotency-wrapped: required-role mutation is strict-not-
idempotent at the decider (a second add hits
`MethodRoleNameAlreadyDeclaredError`); apply Idempotency-Key
support only when cached-success-on-retry semantics are needed.
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe._method_update_handler import make_method_update_handler
from cora.recipe.features.add_method_required_role.command import AddMethodRequiredRole
from cora.recipe.features.add_method_required_role.decider import decide


class Handler(Protocol):
    """Callable interface every add_method_required_role handler implements."""

    async def __call__(
        self,
        command: AddMethodRequiredRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _extra_log_fields(command: AddMethodRequiredRole) -> dict[str, Any]:
    return {
        "role_name": command.requirement.role_name.value,
        "family_id": str(command.requirement.family_id),
        "required_ports_count": len(command.requirement.required_ports),
        "optional": command.requirement.optional,
    }


def bind(deps: Kernel) -> Handler:
    """Build an add_method_required_role handler closed over the shared deps."""
    return make_method_update_handler(
        deps,
        command_name="AddMethodRequiredRole",
        log_prefix="add_method_required_role",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )
