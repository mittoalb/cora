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
(Setpoint/Action/Check rows) live on a substream parallel to 6f-5b
RunReading; step bodies do NOT fold into Procedure state.

## Phase 10c-a scope

Minimal Procedure: id + name + kind + target_asset_ids +
parent_run_id (optional) + status. Two slices ship in 10c-a:
`register_procedure` (genesis -> Defined) and `get_procedure` (read).
Full FSM (Running / Completed / Aborted / Truncated transitions) +
per-step substream land in 10c-b. Projection + list_procedures land
in 10c-c.

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
precedent as `SubjectStatus` / `CapabilityStatus` / `AssetLifecycle`.

## Procedure.kind shape -- bare str (mirror Supply.kind iter-1 lock)

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
shared `validate_bounded_text` helper hoisted in 6e-1
(`cora.infrastructure.bounded_text`).

## target_asset_ids -- eventual-consistency stance

The decider does NOT verify each Asset id refers to a real Asset
stream. Same precedent as Trust's Conduit zone refs (3b), Asset
parent refs (5b), and Method's needs_capabilities (6a). Empty
target_asset_ids is allowed (a procedure that doesn't act on a
specific Asset, e.g. facility-envelope beam-mode change). Existence
+ Decommissioned-lifecycle gating happens at start_procedure time
in 10c-b via `ProcedureStartContext` (mirrors `RunStartContext`
from Run 6f-1).

## parent_run_id -- standalone or Phase-of-Run

`parent_run_id: UUID | None` resolves the Phase aggregate question
flagged in [[project_run_parameters_design]] §6g-c (which said "the
Phase aggregate (10c, Operation BC) will hold the start/stop event
pair"). Resolution: a Phase IS a Procedure with `parent_run_id`
set. Standalone Procedures (bakeouts, calibration sweeps run
between Runs) have `parent_run_id = None`. The aggregate is one;
the binding is the discriminator.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

PROCEDURE_NAME_MAX_LENGTH = 200
PROCEDURE_KIND_MAX_LENGTH = 50
PROCEDURE_ABORT_REASON_MAX_LENGTH = 500


class ProcedureStatus(StrEnum):
    """The Procedure's lifecycle state.

    Five values declared day one for forward-compat
    (additive-state pattern; pre-10c-b events fold cleanly because
    only DEFINED is reachable after register_procedure):

      - `Defined`     -- registration-time genesis; pre-execution.
                          Operator can edit / inspect / submit for
                          review (future Decision BC integration).
                          Cannot accept step events yet.
      - `Running`     -- post-start_procedure (lands 10c-b). Step
                          events accepted via append_procedure_step.
      - `Completed`   -- happy path via complete_procedure (10c-b).
                          Strict-not-idempotent.
      - `Aborted`     -- emergency exit via abort_procedure (10c-b).
      - `Truncated`   -- retroactive cleanup via truncate_procedure
                          (10c-c). Mirrors RunTruncated from 6f-4.

    `Verifying` and `Held / Resumed` are deliberately NOT in this
    enum. Per [[project_operation_design]] standards-corpus research:
    `Verifying` is NOT standards-blessed at FSM level (PackML uses
    `Completing` for closeout/check work; OPC UA Programs has no
    Verify state). Per-step Check happens within Running synchronously
    (via the Step substream's check_passed field at 10c-b). Held /
    Resumed deferred until pilot operator feedback surfaces a need.

    Naming convention (per Run BC 6f-2 gate review): gerund /
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

    Free-form 1-50 chars in 10c-a; future promotion to closed StrEnum
    is a watch item per [[project_operation_design]]. Raised by the
    `register_procedure` decider via `validate_bounded_text`, NOT by
    a `__post_init__` (kind is a bare `str` on Procedure state, not
    a VO; mirrors Supply.kind iter-1 lock).
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
    the shared `validate_bounded_text` helper hoisted in 6e-1 (see
    `cora.infrastructure.bounded_text`).
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
    Per-step records (Setpoint/Action/Check) live on a substream at
    10c-b; the step bodies do NOT fold into this state.

    `id` is the stable opaque handle. `name` is operator-readable.
    `kind` is the free-form ISA-106 procedure-kind discriminator
    (bakeout / calibration / alignment / etc.); bare str per the
    Supply.kind iter-1 lock precedent.

    `target_asset_ids` is a frozenset of Asset ids the procedure
    acts on. Mirrors `Plan.asset_ids` shape from 6e-1; eventual-
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
    in 10c-b when first step lands), expected-step-count for
    progress projections, etc. All land with safe defaults via the
    additive-state pattern.
    """

    id: UUID
    name: ProcedureName
    kind: str
    target_asset_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: ProcedureStatus = ProcedureStatus.DEFINED
    parent_run_id: UUID | None = None
