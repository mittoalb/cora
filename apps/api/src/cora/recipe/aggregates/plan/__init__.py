"""Plan aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.recipe.features.<verb>_plan/` and import from here for state
and event types. The `PlanBindingContext` cross-aggregate value
object lives at `cora.recipe.features.define_plan.context` (slice-
local; only define_plan needs it today; future cross-validating
slices may reuse or get their own context shape).
"""

from cora.recipe.aggregates.plan.events import (
    PlanDefaultParametersUpdated,
    PlanDefined,
    PlanDeprecated,
    PlanEvent,
    PlanVersioned,
    PlanWireAdded,
    PlanWireRemoved,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.recipe.aggregates.plan.evolver import evolve, fold
from cora.recipe.aggregates.plan.parameters_validation import (
    validate_default_parameters_against_method_schema,
)
from cora.recipe.aggregates.plan.read import load_plan
from cora.recipe.aggregates.plan.state import (
    PLAN_NAME_MAX_LENGTH,
    PLAN_VERSION_TAG_MAX_LENGTH,
    WIRE_PORT_NAME_MAX_LENGTH,
    AssetDecommissionedError,
    InvalidPlanDefaultParametersError,
    InvalidPlanError,
    InvalidPlanNameError,
    InvalidPlanVersionTagError,
    InvalidWireError,
    MethodDeprecatedError,
    Plan,
    PlanAlreadyExistsError,
    PlanCannotDeprecateError,
    PlanCannotVersionError,
    PlanCapabilitiesNotSatisfiedError,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
    PlanWireAlreadyExistsError,
    PlanWireAssetNotBoundError,
    PlanWireDirectionMismatchError,
    PlanWireNotFoundError,
    PlanWirePortNotFoundError,
    PlanWireSelfLoopError,
    PlanWireSignalTypeMismatchError,
    PlanWireTargetAlreadyConnectedError,
    PracticeDeprecatedError,
    Wire,
)
from cora.recipe.aggregates.plan.wires_validation import validate_wire_endpoints

__all__ = [
    "PLAN_NAME_MAX_LENGTH",
    "PLAN_VERSION_TAG_MAX_LENGTH",
    "WIRE_PORT_NAME_MAX_LENGTH",
    "AssetDecommissionedError",
    "InvalidPlanDefaultParametersError",
    "InvalidPlanError",
    "InvalidPlanNameError",
    "InvalidPlanVersionTagError",
    "InvalidWireError",
    "MethodDeprecatedError",
    "Plan",
    "PlanAlreadyExistsError",
    "PlanCannotDeprecateError",
    "PlanCannotVersionError",
    "PlanCapabilitiesNotSatisfiedError",
    "PlanDefaultParametersUpdated",
    "PlanDefined",
    "PlanDeprecated",
    "PlanEvent",
    "PlanName",
    "PlanNotFoundError",
    "PlanStatus",
    "PlanVersioned",
    "PlanWireAdded",
    "PlanWireAlreadyExistsError",
    "PlanWireAssetNotBoundError",
    "PlanWireDirectionMismatchError",
    "PlanWireNotFoundError",
    "PlanWirePortNotFoundError",
    "PlanWireRemoved",
    "PlanWireSelfLoopError",
    "PlanWireSignalTypeMismatchError",
    "PlanWireTargetAlreadyConnectedError",
    "PracticeDeprecatedError",
    "Wire",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_plan",
    "to_payload",
    "validate_default_parameters_against_method_schema",
    "validate_wire_endpoints",
]
