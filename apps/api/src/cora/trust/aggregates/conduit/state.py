"""Conduit aggregate state, value objects, and domain errors.

Per ISA-99, a Conduit is a governed communications path between two
Zones. Each Conduit has its own SL-T (Security Level Target) and an
agreed contract describing what may flow through it; runtime
traversal events accumulate against the Conduit's substream.

Phase 3b keeps Conduit minimal: `id` + `name` + the two endpoint zone
IDs. SL-T, contract, and traversal substream land alongside the
slices that exercise them (Policy evaluation needs SL-T; runtime gate
checks emit traversal events). Status lifecycle
(`Defined → Active → Modified → Archived`, per BC-map) follows the
same additive-state pattern as Zone — fields default in the evolver
when added.

**No referential integrity at command time.** `source_zone_id` and
`target_zone_id` are stored as primitives without verifying the
referenced Zones exist. This is the deliberate event-sourcing
posture: aggregate boundaries are transactional consistency
boundaries, and Conduit cannot transactionally consult Zone state.
A typo at the API layer creates a "dangling" Conduit. Two mitigations
arrive later: (1) the eventual-consistency view (a projection that
filters out conduits whose endpoints don't resolve), and (2) Policy
evaluation in 3c, which is the natural home for "is this Conduit
usable" runtime checks.

Endpoint naming (`source` / `target`) is for clarity at the API
layer; the conduit itself is undirected per ISA-99 (a comms path
between two zones, not a one-way arrow). If future use cases need
explicit directionality, add a `direction` enum field; today the
ordering is just convention, not enforced semantics.
"""

from dataclasses import dataclass
from uuid import UUID

CONDUIT_NAME_MAX_LENGTH = 200


class InvalidConduitNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Conduit name must be 1-{CONDUIT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class ConduitAlreadyExistsError(Exception):
    """Attempted to define a conduit whose stream already has events."""

    def __init__(self, conduit_id: UUID) -> None:
        super().__init__(f"Conduit {conduit_id} already exists")
        self.conduit_id = conduit_id


@dataclass(frozen=True)
class ConduitName:
    """Display name for a conduit. Trimmed; 1-200 chars.

    Third occurrence of the same trimmed-bounded-name VO pattern
    (after `ActorName` and `ZoneName`). Each kept distinct so
    invariants can diverge per aggregate; if all three stay
    byte-identical and a fourth appears, hoist a `BoundedName`
    factory to a cross-BC value-objects module.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > CONDUIT_NAME_MAX_LENGTH:
            raise InvalidConduitNameError(self.value)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Conduit:
    """Aggregate root: a governed comms path between two Trust zones."""

    id: UUID
    name: ConduitName
    source_zone_id: UUID
    target_zone_id: UUID
