"""Family aggregate state, status enum, errors, and value objects.

`Family` is the device-class abstraction: WHAT kind of equipment this is,
device-agnostic. Examples: "RotaryStage", "LinearStage", "Camera",
"Scintillator", "Hexapod", "Mirror", "TriggerFPGA". Referenced by
`Asset.families` to declare what classes a Device belongs to, and by
`Method.needs.families` to express a Method's hardware contract;
resolved at `Plan` binding when the contract is matched against
specific `Asset` instances.

## Phase 5i scope (this aggregate)

Direct rename of the prior `Family` aggregate (5a + 5f-2 + 5g-a)
into `Family` per DLM-A [[family-affordance-design-phases-5i-5j-lock]].
Pure rename: same FSM (Defined → Versioned → Deprecated), same
settings_schema field, same lifecycle. Affordance binding lands in 5j
as additive evolution.

The word "Family" is reserved for the future Recipe BC operations-
layer aggregate (DLM-B / phase 6k); after 5i ships, "Family" must
not appear in Equipment BC except in dual-match evolver arms recognizing
legacy event-type strings.

## Status as enum-in-state, derived-from-event-type-in-evolver

`FamilyStatus` is a `StrEnum` so the values would serialize naturally
as JSON-friendly strings IF carried in an event payload. Today they
aren't: state holds the enum (typed) and the evolver derives the new
status from the event TYPE — same precedent as `SubjectStatus` /
`ActorDeactivated → is_active=False`.

## Why Family lives in Equipment (not its own BC)

Per the BC map, Family is one of two aggregates in the Equipment BC
(the other is Asset). Family ships first because it's standalone (no
cross-aggregate refs to other Equipment aggregates) and unblocks
Method's `needs.families` contract.

## Bounded-name VO

`FamilyName` follows the trimmed-bounded-name VO pattern; uses the
shared `validate_bounded_text` helper (hoisted in 6e-1).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

FAMILY_NAME_MAX_LENGTH = 200
FAMILY_VERSION_TAG_MAX_LENGTH = 50


class FamilyStatus(StrEnum):
    """The Family's lifecycle state.

    Transitions:
      - Defined -> Versioned        (version_family)
      - (Defined | Versioned) -> Deprecated   (deprecate_family)

    `Defined` is the genesis state set by `define_family`. The enum
    values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidFamilyNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Family name must be 1-{FAMILY_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class FamilyAlreadyExistsError(Exception):
    """Attempted to define a family whose stream already has events."""

    def __init__(self, family_id: UUID) -> None:
        super().__init__(f"Family {family_id} already exists")
        self.family_id = family_id


class FamilyNotFoundError(Exception):
    """Attempted an operation on a family whose stream has no events."""

    def __init__(self, family_id: UUID) -> None:
        super().__init__(f"Family {family_id} not found")
        self.family_id = family_id


class FamilyCannotVersionError(Exception):
    """Attempted to version a family not in `Defined` or `Versioned`.

    Multi-source guard: `version_family` accepts both `Defined` and
    `Versioned`. Only `Deprecated` is rejected (you can't revise a
    deprecated family — un-deprecate first if you want to bring it
    back, though that slice doesn't exist today).
    """

    def __init__(self, family_id: UUID, current_status: "FamilyStatus") -> None:
        super().__init__(
            f"Family {family_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{FamilyStatus.DEFINED.value} or {FamilyStatus.VERSIONED.value}"
        )
        self.family_id = family_id
        self.current_status = current_status


class FamilyCannotDeprecateError(Exception):
    """Attempted to deprecate a family not in `Defined` or `Versioned`."""

    def __init__(self, family_id: UUID, current_status: "FamilyStatus") -> None:
        super().__init__(
            f"Family {family_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{FamilyStatus.DEFINED.value} or {FamilyStatus.VERSIONED.value}"
        )
        self.family_id = family_id
        self.current_status = current_status


class InvalidFamilyVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Family version tag must be 1-{FAMILY_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class FamilyName:
    """Display name for a family. Trimmed; 1-200 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=FAMILY_NAME_MAX_LENGTH,
            error_class=InvalidFamilyNameError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Family:
    """Aggregate root: a device-class family definition.

    `version` is the operator-supplied label of the most recent
    `version_family` call (None until first version). State always
    holds the latest tag — past tags live in the event stream as
    `FamilyVersioned` events.

    `settings_schema` is the optional JSON Schema (Draft 2020-12,
    constrained subset) declaring the shape of `Asset.settings` keys
    this Family "owns". Affordance binding lands in 5j as an
    additional required field.
    """

    id: UUID
    name: FamilyName
    status: FamilyStatus = FamilyStatus.DEFINED
    version: str | None = None
    settings_schema: dict[str, Any] | None = field(default=None)
