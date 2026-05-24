"""Cross-aggregate context the `update_plan_default_parameters` decider
validates against.

`PlanDefaultParametersContext` is built by the
`update_plan_default_parameters` handler from a `load_method` call
before reaching the pure decider. The decider treats
`method_parameters_schema` as opaque domain data and validates the
merged defaults against it without performing any I/O.

Pattern: same shape as `PlanWireContext` (6h) and
`PlanBindingContext` (6e-1). Slice-local module by design; promote
to a shared form only after the rule of three.

`method_parameters_schema` is None when the bound Method's stream
no longer exists OR the Method declared no schema. The strict
validator interprets None plus non-empty defaults as a rejection
("Method declares no parameters_schema"), per the "no contract
therefore reject" anchor documented in [[project_run_parameters_design]].
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlanDefaultParametersContext:
    """Snapshot of upstream Method state at default-parameters validation time."""

    method_parameters_schema: dict[str, Any] | None
