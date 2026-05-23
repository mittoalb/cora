"""Method's update-handler factory (thin wrapper).

Per-aggregate scoping (not BC-wide) matches the Equipment / Asset
precedent: Recipe owns three aggregates (Method / Practice / Plan)
and each gets its own factory in a sibling module rather than
parameterizing one cross-aggregate factory. Hoist trigger: the
3rd cross-BC instance landed (Run + Recipe).

## Method-side knobs closed over

  - `stream_type = "Method"`.
  - `target_id_attr = "method_id"` — every Method transition
    command exposes `method_id: UUID` (DeprecateMethod /
    VersionMethod / UpdateMethodParametersSchema).
  - `unauthorized_error = UnauthorizedError` from the Recipe BC.
  - The four codec functions imported from
    `cora.recipe.aggregates.method`.

`version_method` carries `version_tag: str` alongside
`method_id`, and `update_method_parameters_schema` derives
`schema_present: bool` from the command — both pass an
`extra_log_fields` extractor at bind time so the pre-hoist log
shape is preserved.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.recipe.aggregates.method import (
    MethodEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError


def make_method_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[MethodEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Method slice."""
    return make_update_handler(
        deps,
        stream_type="Method",
        target_id_attr="method_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        extra_log_fields=extra_log_fields,
    )


__all__ = ["make_method_update_handler"]
