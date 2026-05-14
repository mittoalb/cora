"""Plan aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.recipe.features.<verb>_plan/` and import from here for state
and event types. The `PlanBindingContext` cross-aggregate value
object lives at `cora.recipe.features.define_plan.context` (slice-
local; only define_plan needs it today; future cross-validating
slices may reuse or get their own context shape).
"""

from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    PlanDeprecated,
    PlanEvent,
    PlanParameterDefaultsUpdated,
    PlanVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.recipe.aggregates.plan.evolver import evolve, fold
from cora.recipe.aggregates.plan.parameters_validation import (
    validate_parameter_defaults_against_method_schema,
)
from cora.recipe.aggregates.plan.read import load_plan
from cora.recipe.aggregates.plan.state import (
    PLAN_NAME_MAX_LENGTH,
    PLAN_VERSION_TAG_MAX_LENGTH,
    AssetDecommissionedError,
    InvalidPlanError,
    InvalidPlanNameError,
    InvalidPlanParameterDefaultsError,
    InvalidPlanVersionTagError,
    MethodDeprecatedError,
    Plan,
    PlanAlreadyExistsError,
    PlanCannotDeprecateError,
    PlanCannotVersionError,
    PlanCapabilitiesNotSatisfiedError,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
    PracticeDeprecatedError,
)

__all__ = [
    "PLAN_NAME_MAX_LENGTH",
    "PLAN_VERSION_TAG_MAX_LENGTH",
    "AssetDecommissionedError",
    "InvalidPlanError",
    "InvalidPlanNameError",
    "InvalidPlanParameterDefaultsError",
    "InvalidPlanVersionTagError",
    "MethodDeprecatedError",
    "Plan",
    "PlanAlreadyExistsError",
    "PlanCannotDeprecateError",
    "PlanCannotVersionError",
    "PlanCapabilitiesNotSatisfiedError",
    "PlanDefined",
    "PlanDeprecated",
    "PlanEvent",
    "PlanName",
    "PlanNotFoundError",
    "PlanParameterDefaultsUpdated",
    "PlanStatus",
    "PlanVersioned",
    "PracticeDeprecatedError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_plan",
    "to_payload",
    "validate_parameter_defaults_against_method_schema",
]
