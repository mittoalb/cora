"""Pure decider for the `UpdatePlanParameterDefaults` command.

Phase 6g-b. The decider:
  - Raises PlanNotFoundError on empty state
  - Merges the patch into prior parameter_defaults via RFC 7396 semantics
  - Validates the merged result against the supplied
    `method_parameters_schema` (raises InvalidPlanParameterDefaultsError
    on failure; STRICT when method_parameters_schema is None — non-empty
    merged defaults are rejected; mirrors 5g-c's "no Capabilities +
    non-empty settings → reject" anchor; post-6g audit reversal, see
    [[project_run_parameters_design]] §audit-correction)
  - No-ops (returns []) if the merged result equals the current
    parameter_defaults (matches 5g-c precedent: identical re-submission
    carries no audit value)
  - Otherwise emits PlanParameterDefaultsUpdated(plan_id,
    parameter_defaults, occurred_at) with the FULL post-merge dict in
    the payload (NOT the patch — readers reconstruct current state
    without folding back through prior events)

The handler is responsible for loading the Method stream and
passing its `parameters_schema` into `decide` as the
`method_parameters_schema` argument; the decider stays pure (no I/O).
"""

from datetime import datetime
from typing import Any

from cora.infrastructure.json_merge_patch import merge_patch
from cora.recipe.aggregates.plan import (
    Plan,
    PlanNotFoundError,
    PlanParameterDefaultsUpdated,
    validate_parameter_defaults_against_method_schema,
)
from cora.recipe.features.update_plan_parameter_defaults.command import (
    UpdatePlanParameterDefaults,
)


def decide(
    state: Plan | None,
    command: UpdatePlanParameterDefaults,
    *,
    method_parameters_schema: dict[str, Any] | None,
    now: datetime,
) -> list[PlanParameterDefaultsUpdated]:
    """Decide the events produced by a Plan.parameter_defaults update."""
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    merged = merge_patch(state.parameter_defaults, command.parameter_defaults_patch)

    validate_parameter_defaults_against_method_schema(merged, method_parameters_schema)

    if merged == state.parameter_defaults:
        return []

    return [
        PlanParameterDefaultsUpdated(
            plan_id=state.id,
            parameter_defaults=merged,
            occurred_at=now,
        )
    ]
