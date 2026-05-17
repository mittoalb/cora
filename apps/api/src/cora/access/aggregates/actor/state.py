"""Actor aggregate state, value objects, and domain errors.

`Actor` is the aggregate root for the Access BC. `ActorName` is a value
object that enforces the display-name invariants (non-empty, trimmed,
length-bounded). All errors raised by the domain layer are
`Exception` subclasses defined here so callers can catch them by type.

## Phase 8f-a additive evolution: `kind` field

`Actor.kind` discriminates `human` from `agent` Actors. Per
[[project_agent_bc_design]], every Agent in the Agent BC has a
corresponding Actor in Access BC sharing the same `id`, with
`kind="agent"`; the cross-BC atomic write in `define_agent` emits
both `ActorRegistered(kind="agent")` and `AgentDefined` in one
transaction. Pre-8f-a `ActorRegistered` events lack the `kind`
field; the evolver folds them with the default `"human"` via
`payload.get("kind", "human")`. Forward-compat additive evolution
per the established convention (no upcaster needed).
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

ACTOR_NAME_MAX_LENGTH = 200


class ActorKind(StrEnum):
    """Discriminates human Actors from agent Actors (Phase 8f-a).

    Two values locked day one:

      - `human` -- registered via `register_actor` (Access BC, Phase 1).
                   Default for pre-8f-a Actor streams (forward-compat).
      - `agent` -- registered via `define_agent` (Agent BC, Phase 8f-a)
                   as part of the cross-BC atomic write.

    Decision.actor_id semantics survive the split: humans and agents
    are both first-class principals through the same Authorize port
    per [[project_architecture]], so `actor_id` reference checks
    work uniformly without polymorphism.
    """

    HUMAN = "human"
    AGENT = "agent"


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


class ActorNotFoundError(Exception):
    """Attempted an operation on an actor whose stream has no events."""

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} not found")
        self.actor_id = actor_id


class ActorAlreadyDeactivatedError(Exception):
    """Attempted to deactivate an actor that is already deactivated."""

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} is already deactivated")
        self.actor_id = actor_id


@dataclass(frozen=True)
class ActorName:
    """Display name for an actor. Trimmed; 1-200 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ACTOR_NAME_MAX_LENGTH,
            error_class=InvalidActorNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Actor:
    """Aggregate root: an identified principal known to CORA.

    `is_active` defaults to True at construction; the evolver sets it
    explicitly when folding ActorRegistered (active) and ActorDeactivated
    (inactive). Old ActorRegistered events from before the field existed
    replay correctly because the evolver supplies the default -- no event
    upcaster needed (the field exists in derived state, not in the
    serialized event payload).

    `kind` defaults to `ActorKind.HUMAN` (Phase 8f-a additive evolution).
    Pre-8f-a events fold via `payload.get("kind", "human")` in the events
    deserializer; this default is the in-memory analogue. Forward-compat.
    """

    id: UUID
    name: ActorName
    is_active: bool = True
    kind: ActorKind = ActorKind.HUMAN
