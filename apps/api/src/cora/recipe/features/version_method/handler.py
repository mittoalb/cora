"""Application handler for the `version_method` slice.

Update-style handler. Canonical body lives in
`cora.recipe._method_update_handler.make_method_update_handler`;
this module is a thin slice-specific bind.

The command's `version_tag: str` is logged alongside `method_id`
via `extra_log_fields`, preserving the pre-hoist log shape for
diagnostic visibility (versioning is the noteworthy event).
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.recipe._method_update_handler import make_method_update_handler
from cora.recipe.features.version_method.command import VersionMethod
from cora.recipe.features.version_method.decider import decide

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every version_method handler implements."""

    async def __call__(
        self,
        command: VersionMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def _extra_log_fields(command: Any) -> dict[str, Any]:
    return {"version_tag": command.version_tag}


def bind(deps: Kernel) -> Handler:
    """Build a version_method handler closed over the shared deps."""
    return make_method_update_handler(
        deps,
        command_name="VersionMethod",
        log_prefix="version_method",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )
