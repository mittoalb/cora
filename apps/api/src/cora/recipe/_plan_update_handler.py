"""Plan's update-handler factory (thin wrapper).

See `cora.recipe._method_update_handler` for the per-aggregate
scoping rationale shared across Recipe's three aggregates.

## Plan-side knobs closed over

  - `stream_type = "Plan"`.
  - `target_id_attr = "plan_id"` — every Plan transition command
    exposes `plan_id: UUID` (DeprecatePlan / VersionPlan).
  - `unauthorized_error = UnauthorizedError` from the Recipe BC.
  - The four codec functions imported from
    `cora.recipe.aggregates.plan`.

`version_plan` carries `version_tag: str` alongside `plan_id`
and passes an `extra_log_fields` extractor at bind time to
preserve the pre-hoist log shape.

## Plan slices that stay longhand

  - `update_plan_default_parameters` (6g-b) loads Plan + owning
    Method to surface `parameters_schema`. Multi-stream load,
    single-stream factory cannot serve.
  - `add_plan_wire` / `remove_plan_wire` (6h) load Plan + the two
    referenced Asset streams to validate wire endpoints. Same
    multi-stream constraint.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError


def make_plan_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[PlanEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one single-stream Plan slice."""
    return make_update_handler(
        deps,
        stream_type="Plan",
        target_id_attr="plan_id",
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


__all__ = ["make_plan_update_handler"]
