"""Application handler for the `abort_procedure` slice.

Update-style handler. Same factory-direct pattern as
complete_procedure (rule-of-three for hoisting a Procedure-specific
update-handler wrapper hasn't fired; 10c-c's truncate_procedure will
trigger it).

The command's `reason` field IS captured on the emitted
`ProcedureAborted` event payload but is intentionally NOT logged at
the handler boundary (mirrors abort_run precedent), so this slice
does not pass `extra_log_fields`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.operation.aggregates.procedure import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
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
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an abort_procedure handler closed over the shared deps."""
    return make_update_handler(
        deps,
        stream_type="Procedure",
        target_id_attr="procedure_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name="AbortProcedure",
        log_prefix="abort_procedure",
        decide_fn=decide,
    )
