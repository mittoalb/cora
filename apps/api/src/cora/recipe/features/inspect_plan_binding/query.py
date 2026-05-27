"""The `InspectPlanBinding` query: intent dataclass for the
preview slice.

Mirrors `DefinePlan`'s upstream inputs minus `name`: the caller
asks "if I were to define a Plan binding Practice P with these
Assets, what would the binding look like?" The handler answers
without emitting any events.

Distinct from `GetPlan`, which reads an already-defined Plan.
This slice is a candidate-input preview; an existing-Plan
diagnostic is a future sibling slice if pilot demands it.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class InspectPlanBinding:
    """Preview a Plan binding without defining it.

    `practice_id` selects the Practice (which in turn pins the
    Method and its Capability template). `asset_ids` is the
    candidate wired-Asset set the operator is considering.
    """

    practice_id: UUID
    asset_ids: frozenset[UUID]
