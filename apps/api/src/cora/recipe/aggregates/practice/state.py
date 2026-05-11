"""Practice aggregate state, value objects, status enum, and domain errors.

`Practice` is the **facility-adapted Method** — the institution's
curated version of a technique class, ready to bind to specific
Asset instances at Plan time. ISA-88 maps it to **Site Recipe**:
the Method (≈ General Recipe) gets adapted at the Site level with
facility-specific equipment, constraints, and operational defaults,
but is still abstract over which specific batch run it serves.

Per the BC map's recipe ladder:
  - Method ≈ General Recipe (vendor / scientific community)
  - **Practice ≈ Site Recipe** (this aggregate; 6d)
  - Plan ≈ Master / Control Recipe (concrete Asset binding; 6e)
  - Run ≈ batch execution (6f)

## Phase 6d-1 scope

Minimal Practice:
  - `id` + `name`
  - `method_id: UUID` — the Method this Practice adapts (eventual-
    consistency stance: existence is NOT verified at decide time;
    same precedent as Method.needs_capabilities and Trust 3b)
  - `site_id: UUID` — the Site-level Asset this Practice belongs to
    (institutional ownership; eventual-consistency: not verified)
  - `status: PracticeStatus` (Defined initially; Versioned /
    Deprecated land in 6d-2)
  - `current_version: str | None` (None until first version_practice)

Additional facets defer to a 6d-3 equivalent if pilot demand
emerges:
  - `additional_capabilities: frozenset[CapabilityId]` (facility-
    specific Capability requirements that go beyond Method's
    needs_capabilities — for example a facility that always pairs
    Tomography with FlyScan)
  - `default_parameters` (parameter envelope dict)
  - `safety_overlay` (free-text or structured operator instructions)
  - `owner` (Actor id; institutional sanctioning authority)

## Why Practice and not just Method.facility_id

ISA-88's Site Recipe layer exists for a reason: a single General
Recipe can have multiple facility-adapted Practices (different
sites, different vendors, different operational defaults), and they
evolve independently. Pinning facility constraints onto Method
itself would force a 1-Method-per-facility model that doesn't
generalize.

## Eventual-consistency stance for cross-aggregate refs

Same precedent as everywhere else (Trust Conduit zone refs in 3b,
Method needs_capabilities in 6a, Asset.capabilities entries in
5f-1): the decider does NOT verify `method_id` refers to a real
Method or `site_id` refers to a real Site-level Asset. Typos
produce "dangling" Practices; downstream Plan binding (6e) is where
the mismatch surfaces.

## Status as enum-in-state, derived-from-event-type-in-evolver

Same precedent as Method (6a) and Capability (5a). The lifecycle
mirrors Method's: Defined → Versioned → Deprecated.

## Ninth bounded-name VO

`PracticeName` is the **ninth** trimmed-bounded-name VO after
Actor / Zone / Conduit / Policy / Subject / Capability / Asset /
Method. The 5a gate-review locked the `BoundedName` factory
extraction as deferred until first per-VO divergence OR ~10
instances. The 10th instance is one bounded-name VO away —
extraction question reopens at that point.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

PRACTICE_NAME_MAX_LENGTH = 200
PRACTICE_VERSION_TAG_MAX_LENGTH = 50


class PracticeStatus(StrEnum):
    """The Practice's lifecycle state.

    Mirrors Method's lifecycle (and Capability's). Transitions land
    per-slice in Phase 6d-2:
      - Defined -> Versioned        (version_practice)
      - (Defined | Versioned) -> Deprecated  (deprecate_practice)

    `Defined` is the genesis state set by `define_practice`. The
    enum values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidPracticeNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Practice name must be 1-{PRACTICE_NAME_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class PracticeAlreadyExistsError(Exception):
    """Attempted to define a practice whose stream already has events."""

    def __init__(self, practice_id: UUID) -> None:
        super().__init__(f"Practice {practice_id} already exists")
        self.practice_id = practice_id


class PracticeNotFoundError(Exception):
    """Attempted an operation on a practice whose stream has no events."""

    def __init__(self, practice_id: UUID) -> None:
        super().__init__(f"Practice {practice_id} not found")
        self.practice_id = practice_id


class PracticeCannotVersionError(Exception):
    """Attempted to version a practice not in `Defined` or `Versioned`.

    Multi-source guard: `version_practice` accepts both `Defined`
    (first revision) and `Versioned` (subsequent revisions). Only
    `Deprecated` is rejected. Same divergence from strict-not-
    idempotent as version_method / version_capability:
    re-versioning with the same tag succeeds (re-attestation is a
    legitimate audit moment).

    Per-transition error class — same naming convention as
    `MethodCannotVersionError` (Recipe 6b) and
    `CapabilityCannotVersionError` (Equipment 5f-2).
    """

    def __init__(self, practice_id: UUID, current_status: "PracticeStatus") -> None:
        super().__init__(
            f"Practice {practice_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{PracticeStatus.DEFINED.value} or {PracticeStatus.VERSIONED.value}"
        )
        self.practice_id = practice_id
        self.current_status = current_status


class PracticeCannotDeprecateError(Exception):
    """Attempted to deprecate a practice not in `Defined` or `Versioned`.

    Multi-source guard. Re-deprecating an already-`Deprecated`
    practice raises (strict-not-idempotent). Mirrors
    MethodCannotDeprecateError shape.
    """

    def __init__(self, practice_id: UUID, current_status: "PracticeStatus") -> None:
        super().__init__(
            f"Practice {practice_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{PracticeStatus.DEFINED.value} or {PracticeStatus.VERSIONED.value}"
        )
        self.practice_id = practice_id
        self.current_status = current_status


class InvalidPracticeVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    InvalidMethodVersionTagError (Recipe 6b) and
    InvalidCapabilityVersionTagError (Equipment 5f-2).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Practice version tag must be 1-{PRACTICE_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class PracticeName:
    """Display name for a practice. Trimmed; 1-200 chars.

    Ninth occurrence of the trimmed-bounded-name VO pattern. The
    BoundedName factory extraction stays deferred per the 5a
    gate-review decision (revisit at first per-VO divergence or
    ~10 instances; 10th is one VO away).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > PRACTICE_NAME_MAX_LENGTH:
            raise InvalidPracticeNameError(self.value)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Practice:
    """Aggregate root: a facility-adapted Method (ISA-88 Site Recipe analog).

    `method_id` is the Method this Practice adapts. `site_id` is the
    Site-level Asset (per Equipment's hierarchy) this Practice
    belongs to. Both are eventual-consistency refs: the decider does
    NOT verify they refer to real aggregates. Mismatch surfaces at
    Plan binding (6e).

    `current_version` mirrors Method's pattern: None until the first
    version_practice call; preserved across deprecation as the audit
    signal of the last revision before deprecation.
    """

    id: UUID
    name: PracticeName
    method_id: UUID
    site_id: UUID
    status: PracticeStatus = PracticeStatus.DEFINED
    current_version: str | None = None
