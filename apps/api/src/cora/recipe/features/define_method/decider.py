"""Pure decider for the `DefineMethod` command.

Pure function: given the current Method state (None for a fresh
stream) and a `DefineMethod` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

## Eventual-consistency stance for needed_families

The decider does NOT verify each Family id refers to a real
Family stream in the event store. Same precedent as Trust's
Conduit zone refs (3b) and Asset parent refs (5b). Typos produce
"dangling" Methods that won't bind at Plan time (6e); structural
validation can be layered at the API boundary if pilot demand
emerges.

Empty `needed_families` is allowed (a Method that needs no
specific equipment family — operationally valid for purely
procedural Methods like "Sample Cleaning").
"""

from datetime import datetime
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityNotFoundError,
    ExecutorShape,
)
from cora.recipe.aggregates.method import (
    METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH,
    InvalidMethodNeededSuppliesError,
    Method,
    MethodAlreadyExistsError,
    MethodDefined,
    MethodName,
)
from cora.recipe.features.define_method.command import DefineMethod


class MethodCapabilityExecutorMismatchError(Exception):
    """Method.capability_id points at a Capability whose executor_shapes
    do not include Method (Phase 6l cross-BC guard).

    Mapped to HTTP 409. Surfaces when define_method binds to a
    Capability that only declares ExecutorShape.PROCEDURE.
    """

    def __init__(self, method_id: UUID, capability_id: UUID) -> None:
        super().__init__(
            f"Method {method_id} cannot bind to Capability {capability_id}: "
            f"Capability.executor_shapes does not include {ExecutorShape.METHOD.value}"
        )
        self.method_id = method_id
        self.capability_id = capability_id


def decide(
    state: Method | None,
    command: DefineMethod,
    *,
    capability: Capability | None,
    now: datetime,
    new_id: UUID,
) -> list[MethodDefined]:
    """Decide the events produced by defining a new method.

    Phase 6l-strict: `capability` is REQUIRED at the call boundary
    (the command's `capability_id` is REQUIRED per Pattern P, so the
    handler always loads it). The kwarg keeps `Capability | None`
    so the decider can raise `CapabilityNotFoundError` directly
    when the load returned None (cross-BC reference points at a
    nonexistent stream). Validates:
      1. capability is not None (Capability stream exists)
         -> CapabilityNotFoundError (404)
      2. capability.executor_shapes contains ExecutorShape.METHOD
         (this Capability accepts Method-shaped executors)
         -> MethodCapabilityExecutorMismatchError (409)
    """
    if state is not None:
        raise MethodAlreadyExistsError(state.id)
    if capability is None:
        raise CapabilityNotFoundError(command.capability_id)
    if ExecutorShape.METHOD not in capability.executor_shapes:
        raise MethodCapabilityExecutorMismatchError(new_id, command.capability_id)
    name = MethodName(command.name)  # validates + trims; raises InvalidMethodNameError
    # Phase 10b: defensive per-element validation for needed_supplies
    # kind strings. Pydantic catches this at the API; this defensive
    # pass protects direct in-process callers (sagas, tests) AND
    # trims each kind so persisted bytes are deterministic. Bound
    # mirrors Supply's own InvalidSupplyKindError shape.
    trimmed_supplies: list[str] = []
    for kind in command.needed_supplies:
        trimmed = validate_bounded_text(
            kind,
            max_length=METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH,
            error_class=InvalidMethodNeededSuppliesError,
        )
        trimmed_supplies.append(trimmed)
    return [
        MethodDefined(
            method_id=new_id,
            name=name.value,
            needed_families=list(command.needed_families),
            needed_supplies=trimmed_supplies,
            capability_id=command.capability_id,
            occurred_at=now,
        )
    ]
