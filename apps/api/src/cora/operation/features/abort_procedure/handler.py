"""Application handler for the `abort_procedure` slice.

Update-style handler. Canonical body lives in
`cora.operation._procedure_update_handler.make_procedure_update_handler`;
this module is a thin slice-specific bind. Hoisted at 10c-c when
truncate_procedure landed as the third Procedure update slice
(rule-of-three trigger fired).

The command's `reason` field IS captured on the emitted
`ProcedureAborted` event payload but is intentionally NOT logged at
the handler boundary (mirrors abort_run / Subject discard / Asset
condition precedent), so this slice does not pass `extra_log_fields`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._procedure_update_handler import make_procedure_update_handler
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.abort_procedure.decider import decide


class Handler(Protocol):
    """Callable interface every abort_procedure handler implements."""

    async def __call__(
        self,
        command: AbortProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """abort_procedure handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: AbortProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an abort_procedure handler closed over the shared deps."""
    return make_procedure_update_handler(
        deps,
        command_name="AbortProcedure",
        log_prefix="abort_procedure",
        decide_fn=decide,
    )
