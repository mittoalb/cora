"""Application handler for the `store_subject` slice.

Update-style handler. Canonical body lives in
`cora.subject._update_handler.make_subject_update_handler`; this
module is a thin slice-specific bind.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.subject._update_handler import make_subject_update_handler
from cora.subject.features.store_subject.command import StoreSubject
from cora.subject.features.store_subject.decider import decide


class Handler(Protocol):
    """Callable interface every store_subject handler implements."""

    async def __call__(
        self,
        command: StoreSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a store_subject handler closed over the shared deps."""
    return make_subject_update_handler(
        deps,
        command_name="StoreSubject",
        log_prefix="store_subject",
        decide_fn=decide,
    )
