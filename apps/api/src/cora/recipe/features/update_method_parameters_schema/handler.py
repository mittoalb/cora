"""Application handler for the `update_method_parameters_schema` slice.

Update-style handler. Canonical body lives in
`cora.recipe._method_update_handler.make_method_update_handler`;
this module is a thin slice-specific bind.

The command's `parameters_schema` is reduced to a `schema_present:
bool` for log-line diagnostic visibility (full schemas are
unsuitable for log lines; the event payload retains the schema).
"""

from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.recipe._method_update_handler import make_method_update_handler
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema.decider import decide


class Handler(Protocol):
    """Callable interface every update_method_parameters_schema handler implements."""

    async def __call__(
        self,
        command: UpdateMethodParametersSchema,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def _extra_log_fields(command: Any) -> dict[str, Any]:
    return {"schema_present": command.parameters_schema is not None}


def bind(deps: Kernel) -> Handler:
    """Build an update_method_parameters_schema handler closed over the shared deps."""
    return make_method_update_handler(
        deps,
        command_name="UpdateMethodParametersSchema",
        log_prefix="update_method_parameters_schema",
        decide_fn=decide,
        extra_log_fields=_extra_log_fields,
    )
