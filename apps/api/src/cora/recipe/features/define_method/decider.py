"""Pure decider for the `DefineMethod` command.

Pure function: given the current Method state (None for a fresh
stream) and a `DefineMethod` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

## Eventual-consistency stance for needs_capabilities

The decider does NOT verify each Capability id refers to a real
Capability stream in the event store. Same precedent as Trust's
Conduit zone refs (3b) and Asset parent refs (5b). Typos produce
"dangling" Methods that won't bind at Plan time (6e); structural
validation can be layered at the API boundary if pilot demand
emerges.

Empty `needs_capabilities` is allowed (a Method that needs no
specific equipment capability — operationally valid for purely
procedural Methods like "Sample Cleaning").
"""

from datetime import datetime
from uuid import UUID

from cora.recipe.aggregates.method import (
    Method,
    MethodAlreadyExistsError,
    MethodDefined,
    MethodName,
)
from cora.recipe.features.define_method.command import DefineMethod


def decide(
    state: Method | None,
    command: DefineMethod,
    *,
    now: datetime,
    new_id: UUID,
) -> list[MethodDefined]:
    """Decide the events produced by defining a new method."""
    if state is not None:
        raise MethodAlreadyExistsError(state.id)
    name = MethodName(command.name)  # validates + trims; raises InvalidMethodNameError
    return [
        MethodDefined(
            method_id=new_id,
            name=name.value,
            needs_capabilities=list(command.needs_capabilities),
            occurred_at=now,
        )
    ]
