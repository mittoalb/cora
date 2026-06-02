"""Pure decider for the `DefinePractice` command.

Pure function: given the current Practice state (None for a fresh
stream) and a `DefinePractice` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

## Eventual-consistency stance for cross-aggregate refs

The decider does NOT verify `method_id` refers to a real Method
stream or `site_id` refers to a real Site-level Asset stream. Same
precedent as Trust Conduit zone refs (3b), Asset parent refs (5b),
Method.needed_family_ids (6a), and Asset.family_ids entries
(5f-1). Mismatch surfaces at Plan binding (6e).
"""

from datetime import datetime
from uuid import UUID

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeAlreadyExistsError,
    PracticeDefined,
    PracticeName,
)
from cora.recipe.features.define_practice.command import DefinePractice


def decide(
    state: Practice | None,
    command: DefinePractice,
    *,
    now: datetime,
    new_id: UUID,
) -> list[PracticeDefined]:
    """Decide the events produced by defining a new practice.

    Invariants:
      - State must be None (genesis-only)
        -> PracticeAlreadyExistsError
      - Name must be valid -> InvalidPracticeNameError
        (via PracticeName VO)
    """
    if state is not None:
        raise PracticeAlreadyExistsError(state.id)
    name = PracticeName(command.name)  # validates + trims; raises InvalidPracticeNameError
    return [
        PracticeDefined(
            practice_id=new_id,
            name=name.value,
            method_id=command.method_id,
            site_id=command.site_id,
            occurred_at=now,
        )
    ]
