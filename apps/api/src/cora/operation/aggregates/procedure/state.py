"""Procedure aggregate state, value objects, status enum, and domain errors.

`Procedure` models one execution of an episodic operational task
(ISA-106 lens): bakeout, calibration sweep, optical alignment,
beam-mode change, recovery procedure, ID maintenance, KB switching.
Per the BC map: instrument-level AND facility-envelope procedures
share this aggregate. No batch identity (distinct from Run BC's
ISA-88 batch lens).

The aggregate is intentionally slim per
[[project_fold_cost_principles]]: identity + name + kind + target
Asset refs + status + optional parent_run_id. Per-step records
(Setpoint/Action/Check rows) live in a Logbook + Entry table parallel
to 6f-5b RunReading (CORA's concrete realisation of the substream
concept; see [[project_logbook_entry_storage]] §Terminology); step
bodies do NOT fold into Procedure state.


Minimal Procedure: id + name + kind + target_asset_ids +
parent_run_id (optional) + status. Initial slices:
`register_procedure` (genesis -> Defined) and `get_procedure` (read).
Full FSM (Running / Completed / Aborted / Truncated transitions) +
per-step logbook follow. Projection + list_procedures follow.

## ProcedureStatus FSM (locked initial)

  Defined -> Running -> Completed | Aborted | Truncated

REVISED from BC map's `Idle -> Starting -> Running -> Verifying ->
Complete | Aborted` per the standards-corpus research at
[[project_operation_design]]: `Verifying` is NOT standards-blessed
at FSM level (PackML uses `Completing` for closeout/check work; OPC
UA Programs has no Verify state); per-step Check happens within
Running; transient states deferred until real async window appears
(Run BC precedent). Held/Resumed deferred to 10c-c per pilot need.

## Status as enum-in-state, derived-from-event-type-in-evolver

`ProcedureStatus` is a `StrEnum`; the values would serialize
naturally as JSON-friendly strings IF carried in an event payload.
State holds the enum (typed); the evolver derives the new status
from the event TYPE (`ProcedureRegistered -> DEFINED` etc.). Same
precedent as `SubjectStatus` / `FamilyStatus` / `AssetLifecycle`.

## Procedure.kind shape -- bare str (mirror Supply.kind lock)

`kind: str` is bare on Procedure state, NOT a VO. Validated at the
decider via `validate_bounded_text` (1-50 chars after trim) and at
the API boundary via Pydantic min_length / max_length. Mirrors
`Supply.kind` exactly:

  1. `kind` will eventually graduate to `ProcedureKind: StrEnum` once
     pilot vocabulary settles (Watch item 7 in
     [[project_operation_design]]). Migration `str -> StrEnum` is a
     clean parser change; `ProcedureKind(VO) -> ProcedureKind(StrEnum)`
     would break every type-annotated call site.
  2. `Supply.kind: str` and `AssetPort.signal_type: str` are the
     in-codebase precedents: bare-str discriminator with inline-
     validation, awaiting future enum promotion.

Documented starter vocabulary lives in [[project_operation_design]]
as guidance, not constraint: bakeout, calibration, alignment,
recovery, beam_mode_change, id_maintenance, kb_switching,
optical_alignment, vacuum_regeneration.

## Twelfth bounded-name VO

`ProcedureName` is the twelfth trimmed-bounded-name VO. Uses the
shared `validate_bounded_text` helper hoisted at the rule-of-three
trigger (`cora.infrastructure.bounded_text`).

## Target_asset_ids -- eventual-consistency stance

The decider does NOT verify each Asset id refers to a real Asset
stream. Same precedent as Trust's Conduit zone refs (3b), Asset
parent refs (5b), and Method's needed_families (6a). Empty
target_asset_ids is allowed (a procedure that doesn't act on a
specific Asset, for example facility-envelope beam-mode change). Existence
+ Decommissioned-lifecycle gating happens at start_procedure time
via `ProcedureStartContext` at start_procedure time (mirrors
`RunStartContext` from the Run BC).

## Parent_run_id -- standalone or Phase-of-Run

`parent_run_id: UUID | None` resolves the "Phase aggregate" question
flagged in [[project_run_parameters_design]] (which said "a Phase
aggregate in Operation BC will hold the start/stop event pair").
Resolution: a Phase IS a Procedure with `parent_run_id` set.
Standalone Procedures (bakeouts, calibration sweeps run between Runs)
have `parent_run_id = None`. The aggregate is one; the binding is
the discriminator.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.infrastructure.logbook import LogbookFieldSpec, LogbookSchema

if TYPE_CHECKING:
    from datetime import datetime

PROCEDURE_NAME_MAX_LENGTH = 200
PROCEDURE_KIND_MAX_LENGTH = 50
PROCEDURE_ABORT_REASON_MAX_LENGTH = 500
PROCEDURE_TRUNCATE_REASON_MAX_LENGTH = 500

# per-Procedure step logbook constants.
LOGBOOK_KIND_STEPS = "steps"
"""Discriminator for the Procedure's per-step logbook.

Used as the `kind` value on `ProcedureStepsLogbookOpened` events. One
Procedure has at most one steps logbook (lazy open-on-first-write);
future distinct Procedure-side logbook kinds (operator-action audit,
hazard observations) would land as separate constants and separate
state fields, not as additional values for the same kind. Mirrors
LOGBOOK_KIND_READING from Run BC."""

# Closed enum for the `step_kind` discriminator on per-step rows.
# The three values are CORA's rename of ISA-106's canonical
# Command/Perform/Verify triplet (renamed to avoid CQRS Command
# collision per [[project_operation_design]]). Future-additive
# operational vocabulary (for example "wait", "rollback") lands as
# code edits, not migrations (table column is plain TEXT, not a
# CHECK-constrained enum, mirroring Run BC's sampling_procedure
# precedent).
StepKind = Literal["setpoint", "action", "check"]
STEP_KIND_VALUES: frozenset[str] = frozenset({"setpoint", "action", "check"})

# Schema declaration for the steps logbook. Documentation-grade per
# [[project_logbook_entry_storage]]: declares the entry-row column
# shape so projections can read entry shape uniformly. The shared
# columns are the polymorphic-with-discriminator skeleton; the
# kind-specific body lives in the JSON `payload` column (per-kind
# Pydantic models guard the body shape at the API boundary).
STEPS_LOGBOOK_SCHEMA = LogbookSchema(
    fields={
        "step_kind": LogbookFieldSpec(
            type="string",
            description=(
                "Discriminator for the polymorphic step body. One of: "
                "'setpoint' (control-point change applied), 'action' "
                "(discrete operation performed), 'check' (verification "
                "recorded). CORA's rename of ISA-106's canonical "
                "Command/Perform/Verify triplet. The kind-specific "
                "JSON `payload` column is NOT declared here because "
                "LogbookFieldType is closed over primitives; per-kind "
                "body shape lives at the API layer (Pydantic per-kind "
                "models). See [[project_operation_design]]."
            ),
        ),
        "sampled_at": LogbookFieldSpec(
            type="datetime",
            description=(
                "phenomenonTime: when the step physically happened in "
                "the field (operator-recorded or instrument-clock)."
            ),
        ),
        "occurred_at": LogbookFieldSpec(
            type="datetime",
            description="When the handler appended the entry (CORA Clock port).",
        ),
        "recorded_at": LogbookFieldSpec(
            type="datetime",
            description="When Postgres wrote the row (DEFAULT now()).",
        ),
    },
    description=(
        "Per-Procedure step entries, polymorphic by step_kind "
        "(setpoint | action | check | future). One row per step; "
        "rows write directly to entries_operation_procedure_steps "
        "via the StepStore port (no per-row event on the Procedure "
        "stream). See [[project_operation_design]]."
    ),
)


class ProcedureStatus(StrEnum):
    """The Procedure's lifecycle state.

    Five values declared day one for forward-compat
    (additive-state pattern; legacy events fold cleanly because
    only DEFINED is reachable after register_procedure):

      - `Defined`     -- registration-time genesis; pre-execution.
                          Operator can edit / inspect / submit for
                          review (future Decision BC integration).
                          Cannot accept step events yet.
      - `Running`     -- post-start_procedure. Step events accepted
                          via append_procedure_step.
      - `Completed`   -- happy path via complete_procedure.
                          Strict-not-idempotent.
      - `Aborted`     -- emergency exit via abort_procedure.
      - `Truncated`   -- retroactive cleanup via truncate_procedure.
                          Mirrors RunTruncated.

    `Verifying` and `Held / Resumed` are deliberately NOT in this
    enum. Per [[project_operation_design]] standards-corpus research:
    `Verifying` is NOT standards-blessed at FSM level (PackML uses
    `Completing` for closeout/check work; OPC UA Programs has no
    Verify state). Per-step Check happens within Running synchronously
    (via the Step logbook's check_passed field). Held / Resumed
    deferred until pilot operator feedback surfaces a need.

    Naming convention (per Run BC gate review): gerund /
    adjective for active steady-states (matches PackML / Bluesky);
    past-participle for terminals. `Defined` is past-participle (a
    procedure WAS defined); `Running` is gerund-as-adjective; the
    rest are past-participle terminals.

    Enum values are PascalCase strings (matches BC-map status
    vocabulary; log lines and DTOs read naturally without mapping).
    """

    DEFINED = "Defined"
    RUNNING = "Running"
    COMPLETED = "Completed"
    ABORTED = "Aborted"
    TRUNCATED = "Truncated"


class InvalidProcedureNameError(ValueError):
    """The supplied procedure name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure name must be 1-{PROCEDURE_NAME_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class InvalidProcedureKindError(ValueError):
    """The supplied procedure kind is empty, whitespace-only, or too long.

    Free-form 1-50 chars today; future promotion to closed StrEnum
    is a watch item per [[project_operation_design]]. Raised by the
    `register_procedure` decider via `validate_bounded_text`, NOT by
    a `__post_init__` (kind is a bare `str` on Procedure state, not
    a VO; mirrors Supply.kind lock).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure kind must be 1-{PROCEDURE_KIND_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class ProcedureAlreadyExistsError(Exception):
    """Attempted to register a procedure whose stream already has events."""

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(f"Procedure {procedure_id} already exists")
        self.procedure_id = procedure_id


class ProcedureNotFoundError(Exception):
    """Attempted an operation on a procedure whose stream has no events."""

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(f"Procedure {procedure_id} not found")
        self.procedure_id = procedure_id


class ProcedureAssetDecommissionedError(Exception):
    """Procedure's target Assets include one or more Decommissioned at start.

    Re-validation of Asset state at start_procedure (NOT just register-
    time snapshot). If a target Asset got decommissioned between
    register_procedure and start_procedure, the Procedure can't proceed
    against the now-tombstoned Asset. Mirrors `RunAssetDecommissionedError`.
    Mapped to HTTP 409.
    """

    def __init__(self, asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot start Procedure: the following target Assets are "
            f"Decommissioned: {[str(a) for a in asset_ids]}"
        )
        self.asset_ids = asset_ids


class ProcedureCapabilityExecutorMismatchError(Exception):
    """Procedure.capability_id points at a Capability whose executor_shapes
    do not include Procedure (cross-BC guard).

    Mapped to HTTP 409. Mirrors `MethodCapabilityExecutorMismatchError`.
    Surfaces when register_procedure binds to a
    Capability that only declares `ExecutorShape.METHOD`.
    """

    def __init__(self, procedure_id: UUID, capability_id: UUID) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot bind to Capability {capability_id}: "
            f"Capability.executor_shapes does not include Procedure"
        )
        self.procedure_id = procedure_id
        self.capability_id = capability_id


class ProcedureRequiresAvailableSupplyError(Exception):
    """No Supply registered for one of the parent Run's Method.needed_supplies kinds.

    Cross-BC gate: when a Procedure has `parent_run_id` set (Phase-of-Run),
    `start_procedure` inherits the parent Run's Method.needed_supplies
    requirement. This error fires when ZERO non-Decommissioned Supplies
    of a required kind are registered. Standalone Procedures (no
    parent_run_id) skip this gate today; Capability-level needed_supplies
    is a Watch item per [[project_supply_preflight_gate_design]].

    Mirrors `RunRequiresAvailableSupplyError`. Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, kind: str) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot start: no Supply registered for "
            f"required kind {kind!r}. Register a Supply of that kind and mark "
            f"it Available before starting."
        )
        self.procedure_id = procedure_id
        self.kind = kind


class ProcedureSupplyCoverageMismatchError(Exception):
    """Supply registered for the required kind but none are Available.

    Cross-BC gate: at least one Supply of the required kind is
    registered (and not Decommissioned), but all have status in
    {Unknown, Degraded, Unavailable, Recovering}. Operator must mark
    one Available before starting.

    Mirrors `RunSupplyCoverageMismatchError`. Mapped to HTTP 409.
    """

    def __init__(
        self,
        procedure_id: UUID,
        kind: str,
        supply_status_summary: frozenset[tuple[str, str]],
    ) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot start: required kind {kind!r} "
            f"has no Available Supply. Current statuses: "
            f"{sorted(supply_status_summary)}. Mark one Available before starting."
        )
        self.procedure_id = procedure_id
        self.kind = kind
        self.supply_status_summary = supply_status_summary


class ProcedureCannotStartError(Exception):
    """Attempted to start a Procedure not in `Defined`.

    Single-source guard: `start_procedure` accepts only `Defined`.
    Re-starting a `Running` Procedure raises (strict-not-idempotent);
    starting any terminal (Completed | Aborted | Truncated) raises.
    Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be started: currently in status "
            f"{current_status.value}, start requires {ProcedureStatus.DEFINED.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class ProcedureCannotCompleteError(Exception):
    """Attempted to complete a Procedure not in `Running`.

    Single-source guard: `complete_procedure` accepts only `Running`.
    Re-completing a `Completed` Procedure raises (strict-not-idempotent);
    completing any other state (Defined | Aborted | Truncated) raises.
    Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be completed: currently in status "
            f"{current_status.value}, complete requires {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class ProcedureCannotAbortError(Exception):
    """Attempted to abort a Procedure not in `Running`.

    Single-source guard: `abort_procedure` accepts only `Running` (no
    Held state in the Procedure FSM today; deferred to 10c-c per pilot
    need). Aborting a `Defined` Procedure raises (use a different
    workflow, for example: never start it, then leave it Defined or
    extend the FSM with a cancel-defined slice if real); aborting any
    terminal raises (strict-not-idempotent). Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be aborted: currently in status "
            f"{current_status.value}, abort requires {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class ProcedureCannotTruncateError(Exception):
    """Attempted to truncate a Procedure not in `Running`.

    Single-source guard: `truncate_procedure` accepts only `Running`
    today (Held/Resumed deferred to future iteration). Mirrors
    `ProcedureCannotAbortError`'s source set: a Defined Procedure
    hasn't started so there's no execution to truncate; terminal
    Procedures are already closed (re-truncating a `Truncated`
    Procedure raises, strict-not-idempotent). Distinct from Abort
    at the lifecycle layer: Truncate is for Procedures that are
    already de-facto over (interrupted by infrastructure failure,
    operator returning Monday to mark a Friday-evening crash) and
    are being closed retroactively. The system does not detect
    de-facto-dead Procedures itself; operators must call truncate
    explicitly. Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be truncated: currently in status "
            f"{current_status.value}, truncate requires {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class InvalidProcedureTruncateReasonError(ValueError):
    """The supplied truncate reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Sibling of
    `InvalidProcedureAbortReasonError`; same shape, distinct class for
    BC-local HTTP-status registration. Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure truncate reason must be 1-{PROCEDURE_TRUNCATE_REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidProcedureInterruptedAtError(ValueError):
    """The supplied truncate `interrupted_at` is in the future relative to `now`.

    `interrupted_at` is the operator's best guess at when the actual
    interruption happened, separate from `occurred_at` (when the
    truncate command was processed). The two timestamps can be hours
    or days apart for weekend / overnight interruptions, but
    `interrupted_at` MUST not be later than `now`: you cannot have
    been interrupted in the future. Validated defensively at the
    decider; mirrors `InvalidRunInterruptedAtError`. Mapped to HTTP 400.
    """

    def __init__(self, interrupted_at: "datetime", now: "datetime") -> None:
        super().__init__(
            f"interrupted_at {interrupted_at.isoformat()} is in the future "
            f"relative to now {now.isoformat()}"
        )
        self.interrupted_at = interrupted_at
        self.now = now


class InvalidStepKindError(ValueError):
    """The supplied step_kind is not in the allowed set.

    Pydantic catches this at the API boundary via `Literal[...]` on
    the request body. The handler ALSO validates against
    `STEP_KIND_VALUES` so direct in-process callers (sagas, tests)
    get the same protection. Mirrors `InvalidSamplingProcedureError`
    from Run BC. Mapped to HTTP 400.
    """

    def __init__(self, value: str, allowed: frozenset[str]) -> None:
        super().__init__(f"Procedure step_kind must be one of {sorted(allowed)} (got: {value!r})")
        self.value = value
        self.allowed = allowed


class ProcedureStepsLogbookClosedError(Exception):
    """Cannot append step to a Procedure in a terminal status.

    Per [[project_operation_design]] the Procedure FSM's terminals
    (Completed | Aborted | Truncated) implicitly close the steps
    logbook; no explicit `ProcedureStepsLogbookClosed` event is
    emitted. The `append_procedure_step` handler raises this when
    a writer attempts to append after the Procedure has terminated.
    Mirrors `RunReadingLogbookClosedError` from Run BC. Mapped to
    HTTP 409.

    Note: appending to a `Defined` (pre-start) Procedure also raises
    this; steps are only valid in `Running`.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} steps logbook is closed: currently in "
            f"status {current_status.value}; appends require {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class InvalidProcedureAbortReasonError(ValueError):
    """The supplied abort reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    `InvalidRunAbortReasonError`.

    Free-form `str` (1-500 chars). Structured taxonomy is future-additive
    if vocabulary convergence across real aborts surfaces, or if Decision
    BC adopts ProcedureAbort with structured-context queries. Mirrors
    Run BC's posture exactly. Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure abort reason must be 1-{PROCEDURE_ABORT_REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class ProcedureName:
    """Display name for a procedure. Trimmed; 1-200 chars.

    Twelfth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper hoisted at the
    rule-of-three trigger (see `cora.infrastructure.bounded_text`).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=PROCEDURE_NAME_MAX_LENGTH,
            error_class=InvalidProcedureNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class ProcedureTruncateReason:
    """Free-form truncate reason. Trimmed; 1-500 chars.

    Sibling of `ProcedureAbortReason`; same shape (trimmed +
    bounded), distinct class for BC-local HTTP-status registration.
    Mirrors Run BC's `RunTruncateReason`. The on-the-wire
    representation in `ProcedureTruncated.reason` is `str` (post-
    trim); the VO exists at decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=PROCEDURE_TRUNCATE_REASON_MAX_LENGTH,
            error_class=InvalidProcedureTruncateReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class ProcedureAbortReason:
    """Free-form abort reason. Trimmed; 1-500 chars.

    Domain VO (not just `str`) so the decider validates uniformly via
    the shared `validate_bounded_text` helper. The on-the-wire
    representation in `ProcedureAborted.reason` is `str` (post-trim)
    for payload simplicity; the VO exists at decider-input time only.
    Sibling of `RunAbortReason`; same shape, distinct class for
    BC-local HTTP-status registration.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=PROCEDURE_ABORT_REASON_MAX_LENGTH,
            error_class=InvalidProcedureAbortReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Procedure:
    """Aggregate root: one execution of an episodic operational task.

    Slim aggregate per [[project_fold_cost_principles]]: identity +
    name + kind + target Asset refs + status + optional Run binding.
    Per-step records (Setpoint/Action/Check) live in a Logbook + Entry
    table (see [[project_logbook_entry_storage]]); the step
    bodies do NOT fold into this state.

    `id` is the stable opaque handle. `name` is operator-readable.
    `kind` is the free-form ISA-106 procedure-kind discriminator
    (bakeout / calibration / alignment / etc.); bare str per the
    Supply.kind lock precedent.

    `target_asset_ids` is a frozenset of Asset ids the procedure
    acts on. Mirrors `Plan.asset_ids` shape; eventual-
    consistency stance for existence verification. Empty set is
    valid for facility-envelope procedures (beam-mode change) that
    don't act on a specific Asset instance.

    `parent_run_id` resolves the Phase aggregate question (per
    [[project_operation_design]]): None = standalone procedure
    (bakeout, calibration sweep run between Runs); UUID = Phase-of-
    Run (calibration sweep invoked mid-Run, formerly the planned
    "Phase" aggregate from [[project_run_parameters_design]] §6g-c).

    `status` defaults to `ProcedureStatus.DEFINED`: the
    registration-time initial state. The genesis event
    `ProcedureRegistered` carries no status field; the evolver sets
    `DEFINED` from the event type (same convention as
    `SubjectRegistered -> Received` and `SupplyRegistered ->
    Unknown`).

    Future additive facets (per Watch items in
    [[project_operation_design]]): `steps_logbook_id` (lazy-opened
    when first step lands), expected-step-count for
    progress projections, etc. All land with safe defaults via the
    additive-state pattern.
    """

    id: UUID
    name: ProcedureName
    kind: str
    target_asset_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: ProcedureStatus = ProcedureStatus.DEFINED
    parent_run_id: UUID | None = None
    steps_logbook_id: UUID | None = None
    """Lazy-opened on first `append_procedure_step`.

    None until the first step is appended; populated by the
    `ProcedureStepsLogbookOpened` envelope event the handler emits
    on the Procedure stream. Mirrors `Run.reading_logbook_id`.
    Per the lazy-open pattern: no eager open at start_procedure,
    no Closed event (terminal Procedure.status implicitly closes
    via `ProcedureStepsLogbookClosedError`).
    """
    capability_id: UUID | None = field(default=None)
    """Optional binding to the universal Capability template (Recipe
    BC) this Procedure realizes as a Procedure-shaped executor.
    OPTIONAL so pre-binding Procedures keep working without bulk
    migration; a strict follow-up may REQUIRE the binding per
    Pattern P (or accept that ceremony Procedures stay un-bound when
    no Capability template applies). Same additive-state shape as
    Method.capability_id."""
