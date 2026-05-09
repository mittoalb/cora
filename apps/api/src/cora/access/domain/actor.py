"""Actor aggregate state, value objects, and domain errors.

`Actor` is the aggregate root for the Access BC. `ActorName` is a value
object that enforces the display-name invariants (non-empty, trimmed,
length-bounded). All errors raised by the domain layer are
`Exception` subclasses defined here so callers can catch them by type.
"""

from dataclasses import dataclass
from uuid import UUID

ACTOR_NAME_MAX_LENGTH = 200


class InvalidActorNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Actor name must be 1-{ACTOR_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class ActorAlreadyExistsError(Exception):
    """Attempted to register an actor whose stream already has events."""

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} already exists")
        self.actor_id = actor_id


@dataclass(frozen=True)
class ActorName:
    """Display name for an actor. Trimmed; 1-200 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > ACTOR_NAME_MAX_LENGTH:
            raise InvalidActorNameError(self.value)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Actor:
    """Aggregate root: an identified principal known to CORA."""

    id: UUID
    name: ActorName
