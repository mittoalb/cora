"""Visit aggregate state, value objects, enums, and domain errors.

`Visit` is the operational-envelope counterpart to Trust's authz-topology
primitives (Conduit / Policy / Surface / Zone). It represents a team's
allocated time on a Surface for a Policy-scoped purpose: the
operational answer to "who is on this beamline today, doing what, until
when." Distinct from Campaign (scientific composition above Run) and
from Policy (stable authz rule); orthogonal axes, composition through
Surface + Run + Subject.

8-state FSM locked per `[[project_visit_aggregate_design]]`:

    Planned    -> Arrived    (operator explicit gesture; presence
                              tracking is separate per V6 lock)
    Arrived    -> InProgress (operator explicit start)
    InProgress <-> OnHold    (pause / resume cycle; OnHold reserved
                              for genuine envelope pauses: beam dump,
                              equipment fault, safety hold, extended
                              user break -- NOT for nested-child
                              commissioning, where parent stays
                              InProgress and control concern lives on
                              `proj_surface_active_visit`)
    InProgress | OnHold -> Completed   (normal terminal)
    Planned | Arrived   -> Cancelled   (pre-work cancel; never started)
    InProgress | OnHold -> Aborted     (work-started-then-stopped + reason)
    any non-terminal    -> Voided      (FHIR `entered-in-error` analog;
                                        "this Visit should never have
                                        existed", e.g. BSS double-sent)

The aggregate is intentionally slim per `[[project_fold_cost_principles]]`
and the thin-shape lock in `[[project_visit_aggregate_research]]`: 6
owned scalar fields plus 2 collections (presence_entries shipped Phase
gamma, external_refs shipped Phase epsilon API surface but already on
event payload from Phase beta) plus 1 self-FK (part_of_visit_id, Phase
delta API surface, already on event payload).

## Two-tier period split

`planned_start_at` + `planned_end_at` live on STATE (operator-supplied
at registration; decider reads them for invariants such as
`planned_end_at > now()`). `actual_start_at` + `actual_end_at` live on
PROJECTION per `[[project_template_aggregate_timestamps]]` Path C
(derivable from VisitArrived / VisitStarted / Visit{Completed, Cancelled,
Aborted, Voided} event `occurred_at`).

## Lifecycle-via-explicit-gesture only

Visit lifecycle changes via explicit gesture only -- never auto-derived
from Supply / Asset / Safety / Schedule state. Subscriber may emit an
explicit command in response to those BCs' events, but the command is
audit-trail-visible. Direct application of
`[[project_non_determinism_principle]]` V6 lock.

## Bootstrap stance

Visit commands (`RegisterVisit`, `ArriveVisit`, ..., `VoidVisit`) are NOT
in the System Bootstrap Policy seed. The bootstrap seed stays at
`{DefinePolicy, RegisterActor}`; first real admin Policy grants Visit
commands post-bootstrap. See AuthZ matrix in design memo.

## VisitType closed enum

`VisitType` is a closed StrEnum (`user` / `commissioning` / `maintenance`
/ `calibration` / `staff`) following the `Affordance` precedent. Replaces
the sentinel-value anti-pattern (DMagic `--gup 0`, NICOS demo=0).
Adding a 6th type uses CORA's forward-only migration pattern (drop +
re-add CHECK constraint).

## No `Period` VO

CORA has no `Period` VO today; uses separate `*_at` fields per existing
convention. First rule-of-three on `(start_at, end_at)` pairs would hoist
a `Period` VO; not yet.

## Reason fields carry no PII

Free-text `reason` on Held / Cancelled / Aborted / Voided sits in the
immutable event log forever. Operator UI MUST display a "no PII"
placeholder warning. Cannot be grep-enforced (free-text); enforced by
review + UI affordance. Promote to a `VisitTransitionReason` VO with
structured fields at rule-of-three on PII-leakage incidents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.external_ref import ExternalRef

VISIT_REASON_MAX_LENGTH = 500


class VisitStatus(StrEnum):
    """The Visit's lifecycle state.

    Eight values locked day one per `[[project_visit_aggregate_design]]`.

      - `Planned`    -- registered; not yet arrived; presence collection empty
      - `Arrived`    -- operator declared team on-site (or remote-checked-in);
                        no scans run yet
      - `InProgress` -- work has started (first Run, first take_control, OR
                        explicit start_visit)
      - `OnHold`     -- envelope paused (beam dump / equipment fault / safety
                        hold / extended user break); NOT used for
                        commissioning-during-user (parent stays InProgress)
      - `Completed`  -- normal terminal
      - `Cancelled`  -- pre-work cancel (never reached InProgress)
      - `Aborted`    -- work-started-then-stopped (always with reason)
      - `Voided`     -- FHIR entered-in-error analog: "should never have
                        existed" (BSS double-registration, duplicate, etc.)
    """

    PLANNED = "Planned"
    ARRIVED = "Arrived"
    IN_PROGRESS = "InProgress"
    ON_HOLD = "OnHold"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    ABORTED = "Aborted"
    VOIDED = "Voided"


class VisitType(StrEnum):
    """Closed enum classifying the operational nature of a Visit.

    Five values per `[[project_visit_aggregate_design]]`. Replaces the
    sentinel-value anti-pattern (DMagic `--gup 0`, NICOS demo=0).

      - `user`         -- proposal-driven user beamtime
      - `commissioning`-- detector / mechanism commissioning (nested as
                          partOf a parent user Visit per S2 scenario)
      - `maintenance`  -- preventative or corrective maintenance window
      - `calibration`  -- standalone calibration block (CalibrationRevision
                          is the data-side counterpart in Calibration BC)
      - `staff`        -- staff-only work outside a proposal envelope
    """

    USER = "user"
    COMMISSIONING = "commissioning"
    MAINTENANCE = "maintenance"
    CALIBRATION = "calibration"
    STAFF = "staff"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by decider invariants)
# ---------------------------------------------------------------------------


class InvalidVisitPlannedPeriodError(ValueError):
    """`planned_end_at <= planned_start_at` at registration."""

    def __init__(self, planned_start_at: datetime, planned_end_at: datetime) -> None:
        super().__init__(
            f"Visit planned_end_at must be strictly after planned_start_at "
            f"(got start={planned_start_at.isoformat()}, end={planned_end_at.isoformat()})"
        )
        self.planned_start_at = planned_start_at
        self.planned_end_at = planned_end_at


class InvalidVisitReasonError(ValueError):
    """Reason text on hold / cancel / abort / void is empty or too long after trim."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Visit reason must be 1-{VISIT_REASON_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class VisitAlreadyExistsError(Exception):
    """Attempted to register a visit whose stream already has events.

    Per `[[project_genesis_error_classes]]` this class stays un-hoisted:
    per-BC isinstance routing in the BC's exception handler outweighs the
    ~80 LOC saved by hoisting.
    """

    def __init__(self, visit_id: UUID) -> None:
        super().__init__(f"Visit {visit_id} already exists")
        self.visit_id = visit_id


class VisitNotFoundError(Exception):
    """Attempted an operation on a visit whose stream has no events."""

    def __init__(self, visit_id: UUID) -> None:
        super().__init__(f"Visit {visit_id} not found")
        self.visit_id = visit_id


class VisitCannotTransitionError(Exception):
    """Attempted a lifecycle slice from a disqualifying source status.

    One error class covers every lifecycle transition guard (arrive, start,
    hold, resume, complete, cancel, abort, void). Per-slice subclassing
    (Campaign-style `CampaignCannotHoldError` / `CampaignCannotStartError`
    / etc.) is rejected: Visit has 7 lifecycle transitions, 7 byte-similar
    subclasses would be churn. Single class with `requested_transition`
    discriminator preserves the diagnostic message + log-search
    disambiguation (the slice's log_prefix already disambiguates).
    """

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        requested_transition: str,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        permitted_str = " | ".join(s.value for s in permitted_sources)
        super().__init__(
            f"Visit {visit_id} cannot {requested_transition}: currently in status "
            f"{current_status.value}, requires one of {permitted_str}"
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.requested_transition = requested_transition
        self.permitted_sources = permitted_sources


# ---------------------------------------------------------------------------
# Visit aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Visit:
    """Aggregate root: a team's operational envelope on a Surface.

    Slim aggregate per `[[project_visit_aggregate_design]]` thin-shape
    lock. Identity is a stable opaque `id: UUID`.

    `policy_id: UUID` is REQUIRED -- the authz envelope the Visit
    operates under. Trust BC's `Authorize` port already gates commands
    by Policy; Visit references the same Policy so a single source of
    truth answers "is this actor allowed to act in this Visit's
    context."

    `surface_id: UUID` is REQUIRED -- Visit is Surface-scoped (NOT
    Policy-scoped). One Policy may have many Visits (S8 multi-instrument
    case). Each Visit binds to exactly one Surface. Invariant enforced
    at register_visit.

    `type: VisitType` is REQUIRED -- closed enum classifying the
    operational nature. Replaces sentinel-value anti-pattern.

    `planned_start_at` + `planned_end_at` live on STATE (operator-
    supplied at registration; decider may read them for invariants).
    Actual periods live on projection per Path C.

    `part_of_visit_id: UUID | None` is the self-FK for commissioning-
    during-user nesting (Phase delta API surface; field on event payload
    from Phase beta). Constraint at register_visit: child Visit must
    reference parent on the SAME Surface (`VisitPartOfMismatchedSurfaceError`).

    `external_refs: frozenset[ExternalRef]` is the open-scheme anti-
    corruption ref to upstream-deferred concepts (`proposal` / `btr` /
    `visit` / `cycle`). Reuses cross-BC infrastructure. API surface
    exposed in Phase epsilon; defaults empty until then.

    `last_status_reason: str | None` is populated by Held / Cancelled /
    Aborted / Voided events. Carries the audit breadcrumb. Resume
    preserves the prior value.

    Presence is NOT on this aggregate today; it lands as
    `presence_entries: frozenset[PresenceEntry]` in Phase gamma. The
    Visit lifecycle FSM operates independently of presence per V6
    explicit-gesture lock (operator can drive the full FSM without ever
    calling check_in_to_visit).

    No actor field on the aggregate beyond inherited
    `StoredEvent.principal_id` envelope. Audit truth ("who started /
    held / completed / aborted") lives on the event envelope.
    """

    id: UUID
    policy_id: UUID
    surface_id: UUID
    type: VisitType
    planned_start_at: datetime
    planned_end_at: datetime
    part_of_visit_id: UUID | None = None
    external_refs: frozenset[ExternalRef] = field(default_factory=frozenset[ExternalRef])
    status: VisitStatus = VisitStatus.PLANNED
    last_status_reason: str | None = None
