"""Application handler for the `truncate_procedure` slice.

Update-style handler. Canonical body lives in
`cora.operation._procedure_update_handler.make_procedure_update_handler`;
this module is a thin slice-specific bind. The factory was hoisted
in 10c-c at the rule-of-three trigger (this slice + complete + abort).

The command's `reason` and `interrupted_at` fields are captured on
the emitted `ProcedureTruncated` event payload but are intentionally
NOT logged at the handler boundary (matches abort_procedure / Run BC's
truncate_run / Subject discard / Asset condition precedent).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.operation._procedure_update_handler import make_procedure_update_handler
from cora.operation.features.truncate_procedure.command import TruncateProcedure
from cora.operation.features.truncate_procedure.decider import decide

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every truncate_procedure handler implements."""

    async def __call__(
        self,
        command: TruncateProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """truncate_procedure handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: TruncateProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a truncate_procedure handler closed over the shared deps."""
    return make_procedure_update_handler(
        deps,
        command_name="TruncateProcedure",
        log_prefix="truncate_procedure",
        decide_fn=decide,
    )
