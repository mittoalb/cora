"""Subject aggregate state, value objects, status enum, and domain errors.

`Subject` is the entity being measured, observed, or studied. Generic
across science domains: materials samples, biological specimens,
manufactured parts (including in-flight AM prints being formed during
the experiment), astronomical targets, computational subjects.

Subject identity crosses Run boundaries — the same Subject can be
referenced by multiple Runs (in-situ/operando experiments, repeat
measurements, etc.). Sample-environment rigs and sample changers are
`Equipment.Asset`s; the thing being formed/imaged/observed is the
`Subject`.

## Phase 4a scope

Minimal Subject: `id` + `name` + `status` (defaults `Received`).
Status lifecycle (the full transitions) lands in 4b-4d as each
state-transition slice ships. `hazard`, `custody`, `owner`, and the
in-situ-during-Run substream defer to Phase 4f+.

## Status as enum-in-state, derived-from-event-type-in-evolver

`SubjectStatus` is a `StrEnum` so the values would serialize naturally
as JSON-friendly strings IF carried in an event payload. Today they
aren't: state holds the enum (typed) and the evolver derives the new
status from the event TYPE (e.g., folding `SubjectMounted` always
produces `status=MOUNTED`), exactly mirroring the
`ActorDeactivated -> is_active=False` precedent. The status field
never appears in an event payload — the event type IS the
state-change indicator.

The StrEnum-in-state, str-in-payload bridge will only fire if a future
event type genuinely needs to carry an arbitrary status as data (e.g.,
an admin "set-status" command for backfill). When that lands, the
evolver folds via `SubjectStatus(payload["status"])` and the bridge
becomes load-bearing. Until then the bridge is theoretical.

`SubjectRegistered` implies `Received` (genesis state set by the
evolver). Same additive-state pattern as `Actor.is_active`: the
field exists in state with a default, and future events that change
it land additively.

## In-situ subjects

For in-flight subjects (AM prints, in-situ-formed materials),
`Mounted` covers the active-formation period — same status, different
physical interpretation. If this overloading gets confused later,
split into a separate `Forming` state additively (state-level field
with a default; no event upcaster needed).

## Why no fourth bounded-name VO yet (or fifth)

`SubjectName` is the **fifth** trimmed-bounded-name VO after
`ActorName`, `ZoneName`, `ConduitName`, `PolicyName`. The bodies
remain byte-identical at this commit; the BoundedName factory
extraction was deferred from the post-Phase-3 review specifically to
see whether the fifth instance still fits. Reviewing that decision
is a Phase 4a gate-review concern, not part of this slice's domain.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

SUBJECT_NAME_MAX_LENGTH = 200


class SubjectStatus(StrEnum):
    """The Subject's current lifecycle state.

    Transitions land per-slice in Phase 4b+:
      - Received → Mounted        (mount_subject, 4b)
      - Mounted → Measured        (measure_subject, 4c)
      - Mounted | Measured → Removed   (remove_subject, 4c)
      - Removed → Returned | Stored | Discarded   (4d, three slices)

    `Received` is the genesis state set by `register_subject`. The
    enum values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    RECEIVED = "Received"
    MOUNTED = "Mounted"
    MEASURED = "Measured"
    REMOVED = "Removed"
    RETURNED = "Returned"
    STORED = "Stored"
    DISCARDED = "Discarded"


class InvalidSubjectNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Subject name must be 1-{SUBJECT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class SubjectAlreadyExistsError(Exception):
    """Attempted to register a subject whose stream already has events."""

    def __init__(self, subject_id: UUID) -> None:
        super().__init__(f"Subject {subject_id} already exists")
        self.subject_id = subject_id


class SubjectNotFoundError(Exception):
    """Attempted an operation on a subject whose stream has no events."""

    def __init__(self, subject_id: UUID) -> None:
        super().__init__(f"Subject {subject_id} not found")
        self.subject_id = subject_id


class SubjectCannotMountError(Exception):
    """Attempted to mount a subject not in the `Received` state.

    The current state is carried as `current_status` for diagnostics.
    Per-transition error class (matches `ActorAlreadyDeactivatedError`
    naming) — each Subject transition gets its own
    `SubjectCannot<X>Error` rather than one generic
    `SubjectStateTransitionError`. With 7 states and ~6 transitions,
    per-transition is the right granularity for HTTP error mapping
    (each maps to 409) and for log-search clarity.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be mounted: currently in state "
            f"{current_status.value}, mount requires {SubjectStatus.RECEIVED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectCannotMeasureError(Exception):
    """Attempted to measure a subject not in the `Mounted` state.

    Strict semantics: re-measuring an already-`Measured` subject also
    raises (rather than no-op or always-emit). Per-measurement detail
    (which scan, params, results) is out of scope at the aggregate
    level; that lives in `Run` + substreams later. The aggregate-level
    `Measured` status just means "has been measured at least once".

    See `SubjectCannotMountError` docstring for the per-transition-
    error rationale.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be measured: currently in state "
            f"{current_status.value}, measure requires {SubjectStatus.MOUNTED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectCannotRemoveError(Exception):
    """Attempted to remove a subject from a state other than Mounted or Measured.

    First multi-source-state guard in the codebase: `remove_subject`
    accepts BOTH `Mounted` (sample present but not yet measured —
    operator changed mind, removing without measuring) and `Measured`
    (data collected, ready to remove). The decider checks via
    tuple-membership (`status not in (MOUNTED, MEASURED)`); the error
    message lists both allowed source states for diagnostic clarity.

    See `SubjectCannotMountError` docstring for the per-transition-
    error rationale.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be removed: currently in state "
            f"{current_status.value}, remove requires "
            f"{SubjectStatus.MOUNTED.value} or {SubjectStatus.MEASURED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


@dataclass(frozen=True)
class SubjectName:
    """Display name for a subject. Trimmed; 1-200 chars.

    Fifth occurrence of the trimmed-bounded-name VO pattern. Kept
    distinct so invariants can diverge per aggregate; if all five
    stay byte-identical, the post-Phase-4a gate review is the
    moment to revisit `BoundedName` factory extraction (deferred
    in the post-Phase-3 cleanup specifically to see if Subject
    would fit).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > SUBJECT_NAME_MAX_LENGTH:
            raise InvalidSubjectNameError(self.value)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Subject:
    """Aggregate root: the entity being measured / observed / studied."""

    id: UUID
    name: SubjectName
    status: SubjectStatus = SubjectStatus.RECEIVED
