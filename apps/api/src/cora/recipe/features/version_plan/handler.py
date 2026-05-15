"""Application handler for the `version_plan` slice.

Update-style handler. Canonical body lives in
`cora.recipe._plan_update_handler.make_plan_update_handler`;
this module is a thin slice-specific bind.

The command's `version_tag: str` is logged alongside `plan_id`
via `extra_log_fields`, preserving the pre-hoist log shape for
diagnostic visibility.
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.recipe._plan_update_handler import make_plan_update_handler
from cora.recipe.features.version_plan.command import VersionPlan
from cora.recipe.features.version_plan.decider import decide


class Handler(Protocol):
    """Callable interface every version_plan handler implements."""

    async def __call__(
        self,
        command: VersionPlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def _extra_log_fields(command: Any) -> dict[str, Any]:
    return {"version_tag": command.version_tag}


def bind(deps: Kernel) -> Handler:
    """Build a version_plan handler closed over the shared deps."""
    return make_plan_update_handler(
        deps,
        command_name="VersionPlan",
        log_prefix="version_plan",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )
