"""Application handler for the `return_subject` slice.

Update-style handler. Canonical body lives in
`cora.subject._subject_update_handler.make_subject_update_handler`; this
module is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.subject._subject_update_handler import make_subject_update_handler
from cora.subject.features.return_subject.command import ReturnSubject
from cora.subject.features.return_subject.decider import decide


class Handler(Protocol):
    """Callable interface every return_subject handler implements."""

    async def __call__(
        self,
        command: ReturnSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a return_subject handler closed over the shared deps."""
    return make_subject_update_handler(
        deps,
        command_name="ReturnSubject",
        log_prefix="return_subject",
        decide_fn=decide,
    )
