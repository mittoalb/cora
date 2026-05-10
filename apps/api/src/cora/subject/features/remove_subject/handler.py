"""Application handler for the `remove_subject` slice.

Update-style handler. Canonical body lives in
`cora.subject._update_handler.make_subject_update_handler`; this
module is a thin slice-specific bind.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent (second call from `Removed` state hits
`SubjectCannotRemoveError`).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.subject._update_handler import make_subject_update_handler
from cora.subject.features.remove_subject.command import RemoveSubject
from cora.subject.features.remove_subject.decider import decide


class Handler(Protocol):
    """Callable interface every remove_subject handler implements."""

    async def __call__(
        self,
        command: RemoveSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a remove_subject handler closed over the shared deps."""
    return make_subject_update_handler(
        deps,
        command_name="RemoveSubject",
        log_prefix="remove_subject",
        decide_fn=decide,
    )
