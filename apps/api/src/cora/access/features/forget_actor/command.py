"""The `ForgetActor` command — intent dataclass for the PII erasure slice.

`actor_id` is the **target** Actor aggregate whose `actor_profile`
row will be scrubbed + deleted. The principal-id of the invoker
(typically an operator acting on the actor's behalf, or the actor
themselves in a future self-service slice) is supplied separately
by the application handler at call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ForgetActor:
    """Erase the actor_profile PII vault row for an existing actor."""

    actor_id: UUID
