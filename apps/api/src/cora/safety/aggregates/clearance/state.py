"""Clearance aggregate state, value objects, status/kind enums, bindings, and errors.

`Clearance` wraps a facility safety form (APS ESAF, NSLS-II SAF,
ESRF A-form / SAF, MAX IV DUO / ESRA, DLS ERA / PLHD, DESY DOOR,
ALS ESAF, SLAC BTR, SPring-8 Form 9). One unified aggregate carries
form data + lifecycle state + multi-step review chain + the polymorphic
set of CORA aggregates and external IDs the form binds to.

Per [[project_safety_clearance_design]], the design locks:

  - 8-state FSM: `Defined -> Submitted -> UnderReview -> Approved
    -> Active -> Expired | Rejected | Superseded`
  - 12-value `ClearanceKind` StrEnum covering 9 surveyed facilities
  - Multi-binding `frozenset[ClearanceBinding]` covering Subject /
    Asset / Run / Procedure + ExternalBinding(scheme, id) for
    upstream-deferred refs (Proposal / BTR / LabVisit / Session per
    BC-map line 111 anti-corruption pattern)
  - Multi-step review chain via `reviewers: tuple[ReviewerStep, ...]`
    field (NOT additional FSM states)
  - Discriminated-union `HazardClassification` VO at
    `cora.safety.hazard_classification`

## Phase 11a-a scope

State + ClearanceStatus / ClearanceKind StrEnums + ClearanceTitle VO +
ClearanceBinding union + HazardDeclaration + ReviewerStep + 7 errors.
Genesis decider only (`register_clearance`); transition slices land in
11a-b.

## Status as enum-in-state, derived-from-event-type-in-evolver

`ClearanceStatus` is a `StrEnum` mirroring the cross-aggregate convention
(`SubjectStatus`, `CapabilityStatus`, `AssetLifecycle`, `SupplyStatus`,
`ProcedureStatus`). State holds the typed enum; evolver derives status
from event type (`ClearanceRegistered -> DEFINED`).

`ClearanceKind` is locked 12 values day one per the cross-facility
portability research (v3 pass at /tmp/cora_hazard_research_v3.md).
Extending to a 13th facility-form is purely additive.

## Bindings: multi (frozenset), polymorphic (5 typed arms + ExternalBinding)

The `bindings` field on Clearance is a `frozenset[ClearanceBinding]`
because one ESAF covers samples + user equipment + the Run + the
external proposal -- all at once. Single-binding shape would force one
Clearance per binding (artificial); multi-binding is the natural shape.

The 5 typed arms cover CORA-modeled aggregates (Subject / Asset / Run /
Procedure) plus the anti-corruption escape hatch (ExternalBinding) for
upstream-deferred refs CORA does NOT model: Proposal (BC map line 111
defers), BeamtimeRequest, LabVisit (DLS-specific), Session. When CORA
later models any of these as aggregates, ExternalBinding becomes a typed
binding additively.

## Reviewers tuple, NOT additional FSM states

Per the cross-facility portability research: DESY DOOR has a 3-step
review chain (Local Contact -> Beamline Sci+Coordinator -> Safety
Group); NSLS-II has ERC-mediated changes; APS has dual gating
(beamline + ESRB). All fit one `UnderReview` FSM state with each
reviewer step appended to the `reviewers: tuple[ReviewerStep, ...]`
tuple. The FSM stays clean (8 states); the chain length varies per
facility. This keeps the FSM legible and the audit chain expressive.

## Thirteenth bounded-name VO

`ClearanceTitle` is the 13th occurrence of the trimmed-bounded-name
VO pattern (after SubjectName, AssetName, CapabilityName, RunName,
SupplyName, ProcedureName, RecipeName/MethodName/PracticeName/
PlanName, etc.). Uses the shared `validate_bounded_text` helper.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.safety.hazard_classification import HazardClassification, RiskBand

CLEARANCE_TITLE_MAX_LENGTH = 200
CLEARANCE_EXTERNAL_ID_MAX_LENGTH = 100
CLEARANCE_REJECT_REASON_MAX_LENGTH = 500
CLEARANCE_EXPIRE_REASON_MAX_LENGTH = 500
CLEARANCE_REVIEWER_ROLE_MAX_LENGTH = 50
CLEARANCE_REVIEWER_NOTES_MAX_LENGTH = 2000
CLEARANCE_HAZARD_NOTES_MAX_LENGTH = 2000
CLEARANCE_MITIGATION_REF_MAX_LENGTH = 200
CLEARANCE_EXTERNAL_BINDING_SCHEME_MAX_LENGTH = 50
CLEARANCE_EXTERNAL_BINDING_ID_MAX_LENGTH = 200


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClearanceStatus(StrEnum):
    """The Clearance's lifecycle state.

    Eight values locked day one per [[project_safety_clearance_design]]:

      - `Defined`     -- registered, not yet submitted
      - `Submitted`   -- awaiting first reviewer pickup
      - `UnderReview` -- >=1 reviewer step recorded but not terminal
      - `Approved`    -- all required reviewers approved; not yet effective
      - `Active`      -- currently in force; gates Run.start / Procedure.start
      - `Expired`     -- validity window passed OR explicit expire_clearance
      - `Rejected`    -- terminal-bad
      - `Superseded`  -- replaced by amended child (parent_clearance_id link)

    Compresses the union of all 9 surveyed facility-form lifecycles per
    the cross-facility portability research (v3 pass). Multi-step review
    rolls up into UnderReview + the `reviewers: tuple[...]` field; no
    facility introduces states outside this set.
    """

    DEFINED = "Defined"
    SUBMITTED = "Submitted"
    UNDER_REVIEW = "UnderReview"
    APPROVED = "Approved"
    ACTIVE = "Active"
    EXPIRED = "Expired"
    REJECTED = "Rejected"
    SUPERSEDED = "Superseded"


class ClearanceKind(StrEnum):
    """The form-type (template) this Clearance wraps.

    Ten facility-independent form-types covering the 9 surveyed facilities
    (cross-facility portability research v3 at /tmp/cora_hazard_research_v3.md).
    Facility identity is carried separately via `Clearance.facility_asset_id`
    (a reference to the `Asset.Level.Site` for the facility); it is NOT
    smushed into the kind value.

      - `ESAF`     -- Experiment Safety Assessment Form (used by APS + ALS;
                      facility distinguishes between the two)
      - `SAF`      -- Safety Approval Form (used by NSLS-II + ESRF)
      - `AForm`    -- ESRF A-form (per-proposal)
      - `DUO`      -- MAX IV DUO (proposal-level)
      - `ESRA`     -- MAX IV ESRA (per-experiment, pairs with DUO)
      - `ERA`      -- DLS Experiment Risk Assessment (per-session)
      - `PLHD`     -- DLS Personal Lab Hazard Declaration (per-lab-visit)
      - `DOOR`     -- DESY DOOR (per-beamtime)
      - `BTR`      -- SLAC Beam Time Request safety review
      - `Form9`    -- SPring-8 Form 9 (per-visit)

    `(kind=ESAF, facility_asset_id=<APS_SITE_UUID>)` and
    `(kind=ESAF, facility_asset_id=<ALS_SITE_UUID>)` are distinct without
    string-mangling. Two orthogonal concepts (form-type + facility) are
    cleanly separated; no `ESAF_APS` / `ESAF_ALS` smush.

    Per [[project_safety_clearance_design]] §"Facility lives at
    Asset.Level.Site": facility identity is the existing Asset.Site in
    CORA's Equipment hierarchy, NOT a parallel StrEnum. Adding a new
    facility requires no enum change at all (just register a new Site
    Asset). A 13th form-type (rare; the global form-type registry is
    relatively stable) lands as a new enum member.

    Future ClearanceTemplate aggregate (watch item): when first
    per-template body-schema-validation OR template-versioning need
    surfaces, this StrEnum gets replaced by `template_id: UUID`
    referencing a typed `ClearanceTemplate` aggregate (mirrors Capability
    inside Equipment BC). Same trigger pattern as ProcedureTemplate watch
    item in [[project_operation_design]].
    """

    ESAF = "ESAF"
    SAF = "SAF"
    AFORM = "AForm"
    DUO = "DUO"
    ESRA = "ESRA"
    ERA = "ERA"
    PLHD = "PLHD"
    DOOR = "DOOR"
    BTR = "BTR"
    FORM9 = "Form9"


# ---------------------------------------------------------------------------
# Errors (raised at decider; mapped to HTTP via routes.py exception handlers)
# ---------------------------------------------------------------------------


class InvalidClearanceTitleError(ValueError):
    """The supplied title is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Clearance title must be 1-{CLEARANCE_TITLE_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidClearanceExternalIdError(ValueError):
    """The supplied external_id is empty, whitespace-only, or too long.

    `external_id` is the facility-minted regulatory ID (ESAF-12345,
    SAF-67890, etc.). When provided it must be non-empty and bounded;
    None is allowed (the Clearance pre-mint case).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Clearance external_id must be 1-{CLEARANCE_EXTERNAL_ID_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidClearanceBindingsError(ValueError):
    """The supplied bindings frozenset is empty.

    A Clearance with zero bindings can never gate anything; refuse it
    at the boundary so degenerate Clearances don't sit in the projection.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Clearance bindings invalid: {reason}")
        self.reason = reason


class InvalidClearanceValidityWindowError(ValueError):
    """`valid_from` is after `valid_until` (inverted window)."""

    def __init__(self, valid_from: datetime, valid_until: datetime) -> None:
        super().__init__(
            f"Clearance validity window inverted: "
            f"valid_from={valid_from.isoformat()} > "
            f"valid_until={valid_until.isoformat()}"
        )
        self.valid_from = valid_from
        self.valid_until = valid_until


class InvalidClearanceExternalBindingError(ValueError):
    """An ExternalBinding's scheme or id is empty, whitespace-only, or too long."""

    def __init__(self, field_name: str, value: str, max_length: int) -> None:
        super().__init__(
            f"ExternalBinding {field_name} must be 1-{max_length} chars "
            f"after trimming (got: {value!r})"
        )
        self.field_name = field_name
        self.value = value
        self.max_length = max_length


class InvalidClearanceMitigationRefError(ValueError):
    """A mitigation ref string is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Clearance mitigation ref must be 1-{CLEARANCE_MITIGATION_REF_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidClearanceHazardNotesError(ValueError):
    """A HazardDeclaration notes field exceeds the length cap."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"HazardDeclaration notes must be 0-{CLEARANCE_HAZARD_NOTES_MAX_LENGTH} "
            f"chars after trimming (got len: {len(value)})"
        )
        self.value = value


class InvalidClearanceDeclarationTargetError(ValueError):
    """A `HazardDeclaration.target` references a binding NOT in the Clearance's `bindings` set.

    A Clearance gates against its `bindings`; declarations claim hazards
    against specific binding targets within that set. A target outside
    the binding set is incoherent: the Clearance can't gate the
    declaration's claim because the target isn't even in scope. Strict
    enforcement at the decider per the design memo's "subset semantic"
    documentation.
    """

    def __init__(self, target: object) -> None:
        super().__init__(
            f"HazardDeclaration target {target!r} is not present in the Clearance's bindings set"
        )
        self.target = target


class ClearanceAlreadyExistsError(Exception):
    """Attempted to register a clearance whose stream already has events."""

    def __init__(self, clearance_id: UUID) -> None:
        super().__init__(f"Clearance {clearance_id} already exists")
        self.clearance_id = clearance_id


class ClearanceNotFoundError(Exception):
    """Attempted an operation on a clearance whose stream has no events."""

    def __init__(self, clearance_id: UUID) -> None:
        super().__init__(f"Clearance {clearance_id} not found")
        self.clearance_id = clearance_id


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClearanceTitle:
    """Display title for a clearance. Trimmed; 1-200 chars.

    Thirteenth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper hoisted in 6e-1
    (`cora.infrastructure.bounded_text`).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=CLEARANCE_TITLE_MAX_LENGTH,
            error_class=InvalidClearanceTitleError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


# ---------------------------------------------------------------------------
# ClearanceBinding: 5-arm discriminated union (4 typed CORA refs + ExternalBinding)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectBinding:
    """Clearance binds to a Subject (sample). ESAF declares hazards on samples."""

    subject_id: UUID


@dataclass(frozen=True)
class AssetBinding:
    """Clearance binds to an Asset (equipment). ESAF declares hazards on user equipment."""

    asset_id: UUID


@dataclass(frozen=True)
class RunBinding:
    """Clearance binds to a Run. ESAF gates a specific Run's start."""

    run_id: UUID


@dataclass(frozen=True)
class ProcedureBinding:
    """Clearance binds to a Procedure. ESAF gates a Procedure (calibration / bakeout)."""

    procedure_id: UUID


@dataclass(frozen=True)
class ExternalBinding:
    """Clearance binds to an upstream-deferred concept CORA does NOT model.

    Per BC map line 111: Programs / Funding lines / Proposals are
    "consumed via anti-corruption adapter, not modeled internally". Same
    for BeamtimeRequest, LabVisit (DLS-specific), Session. ExternalBinding
    captures the (scheme, id) pair so the Clearance can still gate
    against these references.

    Common schemes: 'proposal' / 'btr' / 'lab_visit' / 'session'.
    Run gains a `external_refs: frozenset[ExternalRef]` field in 11a-c
    so Run.start gating can match ExternalBinding to the Run's
    facility-known refs.
    """

    scheme: str
    id: str

    def __post_init__(self) -> None:
        # Loop var named `attr_name` (not `field_name`) to avoid shadowing the
        # `dataclasses.field` import at module top.
        for attr_name, value, max_length in (
            ("scheme", self.scheme, CLEARANCE_EXTERNAL_BINDING_SCHEME_MAX_LENGTH),
            ("id", self.id, CLEARANCE_EXTERNAL_BINDING_ID_MAX_LENGTH),
        ):
            trimmed = value.strip()
            if not trimmed or len(trimmed) > max_length:
                raise InvalidClearanceExternalBindingError(attr_name, value, max_length)
            object.__setattr__(self, attr_name, trimmed)


ClearanceBinding = SubjectBinding | AssetBinding | RunBinding | ProcedureBinding | ExternalBinding
"""Discriminated union: what a Clearance gates against.

`isinstance` discrimination at the boundary (Pydantic at the API,
payload-shape check at the evolver). Multi-bind via `frozenset` on
Clearance.bindings.
"""


# ---------------------------------------------------------------------------
# HazardDeclaration: a hazard claim against a specific binding target
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HazardDeclaration:
    """A hazard claim (intrinsic descriptor + mitigations) against a binding target.

    Each declaration scopes its claim to ONE of the Clearance's bindings
    (the target). `classifications` is the frozenset of typed
    `HazardClassification` VOs (NFPA704Rating / RiskBand / GHSPictogram /
    SchemeCode -- see `cora.safety.hazard_classification`).

    `mitigations` is a frozenset of free-form ref strings (PPE codes,
    training cert refs, procedure IDs); typed mitigations are deferred
    to the [gap] watch item for separate Mitigation aggregate (the
    four-primitive split's bottom half).

    `notes` is operator-supplied prose, 0-2000 chars (optional).
    """

    target: ClearanceBinding
    classifications: frozenset[HazardClassification] = field(
        default_factory=frozenset[HazardClassification]
    )
    mitigations: frozenset[str] = field(default_factory=frozenset[str])
    notes: str | None = None

    def __post_init__(self) -> None:
        for ref in self.mitigations:
            trimmed = ref.strip()
            if not trimmed or len(trimmed) > CLEARANCE_MITIGATION_REF_MAX_LENGTH:
                raise InvalidClearanceMitigationRefError(ref)
        if self.notes is not None:
            notes_trimmed = self.notes.strip()
            if len(notes_trimmed) > CLEARANCE_HAZARD_NOTES_MAX_LENGTH:
                raise InvalidClearanceHazardNotesError(self.notes)
            object.__setattr__(self, "notes", notes_trimmed if notes_trimmed else None)


# ---------------------------------------------------------------------------
# ReviewerStep: one step in the multi-step review chain
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewerStep:
    """One step in the Clearance's review chain.

    Per the cross-facility portability research, multi-step chains are
    universal across surveyed facilities (DESY DOOR has 3 steps; NSLS-II
    has ERC-mediated changes; APS has dual gating). Modeling each step
    as a tuple element keeps the FSM clean (8 states) while letting the
    chain length vary per facility.

    `step_index` is 0-based and append-only (decider enforces
    `step_index == len(state.reviewers)`); `role` is free-form
    facility-vocabulary (`BeamlineScientist` / `Coordinator` / `ESH` /
    `ESRB` / `LocalContact`); `decision` is one of `Approved` /
    `Rejected` / `RequestedChanges` (validated at API boundary).
    """

    step_index: int
    role: str
    actor_id: UUID
    decision: str
    decided_at: datetime
    notes: str | None = None


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Clearance:
    """Aggregate root: a facility safety-form clearance.

    Slim aggregate per [[project_fold_cost_principles]]: identity +
    typed kind + title + bindings + declarations + risk_band +
    review chain + status + lazy parent / validity / review-cycle
    timestamps. Per-step audit metadata (decided_at, role, decision)
    lives on ReviewerStep tuple entries.

    Per the cross-facility portability research, this single aggregate
    shape is portable across all 9 surveyed facilities (split-form
    facilities like ESRF / MAX IV / DLS get multiple Clearance instances
    per Run, each with its own bindings, NOT a polymorphic Clearance
    aggregate type).

    `id` is the stable opaque CORA UUID. `external_id` is the facility-
    minted regulatory ID (ESAF-12345, SAF-67890, etc.); set lazily once
    the facility approves and assigns. Mirrors PID landscape internal-
    opaque + lazy-external-mint pattern.

    Phase 11a-a ships the Defined-only FSM; transition events are
    declared in events.py but unreachable until 11a-b adds the FSM-
    closure slices.
    """

    id: UUID
    kind: ClearanceKind
    facility_asset_id: UUID  # references the Asset.Level.Site for the facility
    title: ClearanceTitle
    bindings: frozenset[ClearanceBinding]
    declarations: frozenset[HazardDeclaration] = field(default_factory=frozenset[HazardDeclaration])
    risk_band: RiskBand | None = None
    reviewers: tuple[ReviewerStep, ...] = ()
    status: ClearanceStatus = ClearanceStatus.DEFINED
    external_id: str | None = None
    parent_clearance_id: UUID | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    next_review_due_at: datetime | None = None
    last_reviewed_by_actor_id: UUID | None = None
