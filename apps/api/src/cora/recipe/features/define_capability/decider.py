"""Pure decider for the `DefineCapability` command.

Pure function: given the current Capability state (None for a fresh
stream) and a `DefineCapability` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

Invariants:
  - State must be None (capability stream must be fresh)
    -> CapabilityAlreadyExistsError
  - command.code must satisfy the namespace + length rules
    -> InvalidCapabilityCodeError
  - command.name must be 1-200 chars after trimming
    -> InvalidCapabilityNameError
  - command.description (when supplied) must be 0-2000 chars
    -> InvalidCapabilityDescriptionError
  - command.executor_shapes must be non-empty
    -> InvalidExecutorShapesError
  - command.parameters_schema (when supplied) must be a valid
    in-subset JSON Schema -> InvalidCapabilityParametersSchemaError
"""

from datetime import datetime
from uuid import UUID

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityCode,
    CapabilityName,
    RecipeCapabilityDefined,
    validate_capability_parameters_schema,
)
from cora.recipe.aggregates.capability.state import (
    validate_capability_description,
    validate_executor_shapes,
)
from cora.recipe.features.define_capability.command import DefineCapability


def decide(
    state: Capability | None,
    command: DefineCapability,
    *,
    now: datetime,
    new_id: UUID,
) -> list[RecipeCapabilityDefined]:
    """Decide the events produced by defining a new Capability."""
    if state is not None:
        raise CapabilityAlreadyExistsError(state.id)
    code = CapabilityCode(command.code)  # validates namespace + length
    name = CapabilityName(command.name)  # validates 1-200 chars
    description = validate_capability_description(command.description)
    executor_shapes = validate_executor_shapes(command.executor_shapes)
    if command.parameters_schema is not None:
        validate_capability_parameters_schema(command.parameters_schema)
    return [
        RecipeCapabilityDefined(
            capability_id=new_id,
            code=code.value,
            name=name.value,
            description=description,
            required_affordances=command.required_affordances,
            executor_shapes=executor_shapes,
            parameters_schema=command.parameters_schema,
            occurred_at=now,
        )
    ]
