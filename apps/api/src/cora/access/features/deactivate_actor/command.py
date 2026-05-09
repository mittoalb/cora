"""The `DeactivateActor` command — intent dataclass for this slice.

`actor_id` is the **target** Actor aggregate (caller-supplied: the actor
to deactivate). The principal-id of the invoker is supplied separately
by the application handler at call time, not in the command.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeactivateActor:
    """Deactivate an existing actor by id."""

    actor_id: UUID
