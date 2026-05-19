"""Application handler for the `complete_procedure` slice.

Update-style handler. Canonical body lives in
`cora.operation._procedure_update_handler.make_procedure_update_handler`;
this module is a thin slice-specific bind. Hoisted at 10c-c when
truncate_procedure landed as the third Procedure update slice
(rule-of-three trigger fired).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._procedure_update_handler import make_procedure_update_handler
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
        surface_id: UUID = NIL_SENTINEL_ID,
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
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a complete_procedure handler closed over the shared deps."""
    return make_procedure_update_handler(
        deps,
        command_name="CompleteProcedure",
        log_prefix="complete_procedure",
        decide_fn=decide,
    )
