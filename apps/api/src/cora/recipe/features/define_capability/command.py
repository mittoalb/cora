"""The `DefineCapability` command — intent dataclass for this slice.

Carries the FULL declarative contract the caller controls
(code, name, optional description, required_affordances,
executor_shapes, optional parameter_schema). Server-side concerns
(new id, wall-clock timestamp, correlation id, per-event ids) are
injected by the handler from infrastructure ports.

Status is implicit at definition (`Defined`) and not part of the
command — see the Capability aggregate's `state.py` docstring for
the enum-in-state, str-in-event convention.

`required_affordances` and `executor_shapes` are REQUIRED per
Pattern P from [[project-capability-aggregate-design]] (FHIR
R5 minimum-cardinality criterion: required iff necessary to any
understanding of the resource). `executor_shapes` must be non-empty
(a Capability with no executor kinds has no operational meaning);
the decider raises `InvalidExecutorShapesError` on empty input.
"""

from dataclasses import dataclass
from typing import Any

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import ExecutorShape


@dataclass(frozen=True)
class DefineCapability:
    """Define a new universal Capability template at the operations layer."""

    code: str
    name: str
    required_affordances: frozenset[Affordance]
    executor_shapes: frozenset[ExecutorShape]
    description: str | None = None
    parameter_schema: dict[str, Any] | None = None
