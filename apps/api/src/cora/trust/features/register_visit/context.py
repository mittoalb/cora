"""Cross-aggregate context the `register_visit` decider validates against.

Built by the handler from one optional `load_visit` against
`part_of_visit_id`. The decider distinguishes "no partOf asked for"
from "partOf asked for but parent stream empty" by inspecting
`command.part_of_visit_id` directly; the context only carries the
loaded `parent_visit | None`.
"""

from dataclasses import dataclass

from cora.trust.aggregates.visit import Visit


@dataclass(frozen=True)
class RegisterVisitContext:
    """Snapshot of the partOf parent Visit at register-visit command time."""

    parent_visit: Visit | None
