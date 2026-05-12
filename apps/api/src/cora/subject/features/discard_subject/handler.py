"""Application handler for the `discard_subject` slice.

Update-style handler. Canonical body lives in
`cora.subject._update_handler.make_subject_update_handler`; this
module is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.subject._update_handler import make_subject_update_handler
from cora.subject.features.discard_subject.command import DiscardSubject
from cora.subject.features.discard_subject.decider import decide


class Handler(Protocol):
    """Callable interface every discard_subject handler implements."""

    async def __call__(
        self,
        command: DiscardSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a discard_subject handler closed over the shared deps."""
    return make_subject_update_handler(
        deps,
        command_name="DiscardSubject",
        log_prefix="discard_subject",
        decide_fn=decide,
    )
