"""Capability aggregate state, value objects, status enum, and domain errors.

`Capability` is the technique-class capability definition: WHAT a
class of equipment can do, equipment-agnostic. Examples: "Continuous
Rotation Tomography", "X-ray Fluorescence Mapping", "Powder
Diffraction". Referenced by `Recipe.Method.needs.capabilities` to
express a Method's hardware contract; resolved at `Plan` binding
when the contract is matched against specific `Asset` instances.

## Phase 5a scope

Minimal Capability: `id` + `name` + `status` (defaults `Defined`).
`Versioned` and `Deprecated` transitions land in 5f+ (per the BC
map's `Defined → Versioned → Deprecated` lifecycle); for the
pilot, capabilities are defined once and stay Defined. Cross-
facility reusability and PIDINST-style external identifiers defer
to additive phases.

## Status as enum-in-state, derived-from-event-type-in-evolver

`CapabilityStatus` is a `StrEnum` so the values would serialize
naturally as JSON-friendly strings IF carried in an event payload.
Today they aren't: state holds the enum (typed) and the evolver
derives the new status from the event TYPE — same precedent as
`SubjectStatus` / `ActorDeactivated → is_active=False`.

## Why Capability lives in Equipment (not its own BC)

Per the BC map, Capability is one of two aggregates in the
Equipment BC (the other is Asset). This is the first BC where the
SECOND aggregate is the chunky one (Trust shipped its 3 aggregates
one-per-phase with similar weight; Subject had only one). 5a ships
Capability first because it's standalone (no cross-aggregate refs)
and unblocks Recipe.Method's `needs.capabilities` contract; 5b adds
Asset (hierarchy + lifecycle).

## Sixth bounded-name VO

`CapabilityName` is the **sixth** trimmed-bounded-name VO after
`ActorName`, `ZoneName`, `ConduitName`, `PolicyName`, `SubjectName`.
The post-Phase-3 review explicitly deferred the `BoundedName`
factory extraction to "see what the 6th instance does"; gate-
review at the end of 5a is the moment to make that call.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

CAPABILITY_NAME_MAX_LENGTH = 200


class CapabilityStatus(StrEnum):
    """The Capability's lifecycle state.

    Transitions land per-slice in Phase 5f+:
      - Defined -> Versioned        (version_capability)
      - (Defined | Versioned) -> Deprecated   (deprecate_capability)

    `Defined` is the genesis state set by `define_capability`. The
    enum values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidCapabilityNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Capability name must be 1-{CAPABILITY_NAME_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class CapabilityAlreadyExistsError(Exception):
    """Attempted to define a capability whose stream already has events."""

    def __init__(self, capability_id: UUID) -> None:
        super().__init__(f"Capability {capability_id} already exists")
        self.capability_id = capability_id


class CapabilityNotFoundError(Exception):
    """Attempted an operation on a capability whose stream has no events."""

    def __init__(self, capability_id: UUID) -> None:
        super().__init__(f"Capability {capability_id} not found")
        self.capability_id = capability_id


@dataclass(frozen=True)
class CapabilityName:
    """Display name for a capability. Trimmed; 1-200 chars.

    Sixth occurrence of the trimmed-bounded-name VO pattern. Kept
    distinct so invariants can diverge per aggregate; the
    `BoundedName` factory extraction question reopens at this point
    per the post-Phase-3 review's deferred-to-#6 plan.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > CAPABILITY_NAME_MAX_LENGTH:
            raise InvalidCapabilityNameError(self.value)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Capability:
    """Aggregate root: a technique-class capability definition."""

    id: UUID
    name: CapabilityName
    status: CapabilityStatus = CapabilityStatus.DEFINED
