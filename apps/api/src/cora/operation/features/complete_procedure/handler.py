"""Application handler for the `complete_procedure` slice.

Update-style handler. Calls `make_update_handler` directly without a
per-Procedure wrapper -- 10c-b ships only two update slices
(complete_procedure + abort_procedure); rule-of-three for hoisting a
`_procedure_update_handler.py` wrapper hasn't fired. 10c-c's
`truncate_procedure` will be the third trigger; at that point a
`make_procedure_update_handler` thin wrapper lands and these two
slices migrate to it.
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
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.complete_procedure.decider import decide


class Handler(Protocol):
    """Callable interface every complete_procedure handler implements."""

    async def __call__(
        self,
        command: CompleteProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """complete_procedure handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: CompleteProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a complete_procedure handler closed over the shared deps."""
    return make_update_handler(
        deps,
        stream_type="Procedure",
        target_id_attr="procedure_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name="CompleteProcedure",
        log_prefix="complete_procedure",
        decide_fn=decide,
    )
