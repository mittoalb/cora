"""Application handler for the `mount_subject` slice.

Update-style handler. The full canonical body lives in
`cora.subject._update_handler.make_subject_update_handler` (load +
authorize + fold + decide + append, with structured logging at each
boundary). This module is a thin slice-specific bind: it supplies
the command name, log prefix, and decider.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent at the aggregate level (second call hits
`SubjectCannotMountError`); apply only when cached-success-on-retry
semantics are needed. See CONTRIBUTING.md.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.subject._update_handler import make_subject_update_handler
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.decider import decide


class Handler(Protocol):
    """Callable interface every mount_subject handler implements.

    See `register_subject.handler.Handler` for the rationale on the
    optional `causation_id` kwarg (HTTP / MCP entrypoints pass None;
    sagas / process managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: MountSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a mount_subject handler closed over the shared deps."""
    return make_subject_update_handler(
        deps,
        command_name="MountSubject",
        log_prefix="mount_subject",
        decide_fn=decide,
    )
