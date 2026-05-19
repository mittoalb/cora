"""Application handler for the `version_practice` slice.

Update-style handler. Canonical body lives in
`cora.recipe._practice_update_handler.make_practice_update_handler`;
this module is a thin slice-specific bind.

The command's `version_tag: str` is logged alongside
`practice_id` via `extra_log_fields`, preserving the pre-hoist
log shape for diagnostic visibility.
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe._practice_update_handler import make_practice_update_handler
from cora.recipe.features.version_practice.command import VersionPractice
from cora.recipe.features.version_practice.decider import decide


class Handler(Protocol):
    """Callable interface every version_practice handler implements."""

    async def __call__(
        self,
        command: VersionPractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _extra_log_fields(command: Any) -> dict[str, Any]:
    return {"version_tag": command.version_tag}


def bind(deps: Kernel) -> Handler:
    """Build a version_practice handler closed over the shared deps."""
    return make_practice_update_handler(
        deps,
        command_name="VersionPractice",
        log_prefix="version_practice",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )
