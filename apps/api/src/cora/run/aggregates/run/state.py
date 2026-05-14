"""Run aggregate state, value objects, status enum, and domain errors.

`Run` is the actual-execution layer in CORA's recipe ladder
(Method → Practice → Plan → **Run**). One Run = one execution
instance with batch identity, FSM, audit trail, and references to
the bound Plan + (optional) Subject.

Per the BC map, Run is a **Lifecycle Aggregate**: terminal states
(`Completed`, `Aborted`, `Stopped`, `Truncated`) end the stream
naturally. After 6f-2+ ships those, the design implication (per
`project_fold_cost_principles.md`) is that the completion event
should carry summary state so downstream consumers don't have to
re-fold per-step history just to ask "what happened in Run X?".

## Aggregate scope

Run state:
  - `id` + `name` (RunName: 11th bounded-name VO)
  - `plan_id: UUID` — eventual-consistency ref to the Plan being
    executed; loaded at handler-load time for re-validation
  - `subject_id: UUID | None` — the Subject being measured, or
    None for dark-field / flat-field calibration runs (per
    beamline-domain convention; calibration data is consumed
    alongside sample data within the same analysis pipeline)
  - `status: RunStatus` (`Running` only at 6f-1; transitions in
    6f-2+)

The active steady-state is named `Running` (not `Started`) per
the gerund/adjective convention used by ISA-88 / PackML
(`Execute`) and Bluesky beamline software (`running`). Past-
participle names like `Started` linguistically suggest a point-
in-time event, not an ongoing state — those belong on event
classes (`RunStarted` is correctly named) but not on the status
enum. See the 6f-2 gate review for the rename rationale.

Run does NOT directly reference Asset(s) — those are reachable via
`plan.asset_ids`. State stays slim per Q4-style reasoning: only
fields decider invariants need.

## Why subject_id is Optional (not Required)

Beamline operations frequently include calibration runs that have
no Subject:
  - Dark-field: detector measures background noise (no beam, no sample)
  - Flat-field: detector measures beam profile (beam, no sample)
  - Energy calibration: standard reference samples (different from
    user Subject)

These produce data consumed by the analysis pipeline for actual
sample Runs. They share the Run lifecycle, audit, and FSM with
sample runs — only the Subject binding differs. Modeling them as
the same aggregate with `subject_id: UUID | None` is cleaner than
a discriminator field or a separate `CalibrationRun` aggregate.

Confirmed by Bluesky / beamline-software domain research: dark-
field acquisition is "an integral part of beamline operations".
Subject-optional Run is the right modeling choice.

## Cross-aggregate validation at Run-start (gate-review Q2 / Q5)

The `start_run` handler pre-loads Plan + Subject (if subject_id) +
each bound Asset (from `plan.asset_ids`), bundles them into a
`RunStartContext`, and hands it to the pure decider. The decider
treats them as opaque domain data and validates:

  - state must be None (defensive: stream collision)
  - plan must not be Deprecated
  - subject (if present) must be in {Mounted, Measured}
  - no bound Asset may be Decommissioned
  - capability superset RE-VALIDATED: union(asset.capabilities) ⊇
    method.needs_capabilities (from current Asset state, not the
    Plan-bind snapshot — drift is real and Run is the last gate)
  - name validation (via RunName VO)

Same canonical pattern as `PlanBindingContext` (6e-1). Documented
in CONTRIBUTING.md as the cross-aggregate-validation idiom.

## Status as enum-in-state, derived-from-event-type-in-evolver

Same precedent as Method / Practice / Plan / Capability /
Subject / Asset. RunStatus is a `StrEnum`; the evolver derives
the new status from the event TYPE per match arm. Status is NOT
carried in event payloads.

## Eleventh bounded-name VO

`RunName` calls the shared `validate_name` helper hoisted in
6e-1 (`cora.infrastructure.name`). Same pattern as the prior 10.

## Known gaps documented (gate-review Q3)

  - **No Supply availability check**: Track B Supply BC not shipped;
    Run-start does NOT verify beam/power/gas availability. Lands
    when Supply BC ships.
  - **No Decision approval check**: Decision BC not shipped; Run-
    start does NOT require an Approved Decision. Lands when
    Decision BC ships.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.infrastructure.name import validate_name

RUN_NAME_MAX_LENGTH = 200
RUN_ABORT_REASON_MAX_LENGTH = 500
RUN_STOP_REASON_MAX_LENGTH = 500
RUN_TRUNCATE_REASON_MAX_LENGTH = 500


class RunStatus(StrEnum):
    """The Run's lifecycle state.

    6f-4 closes the FSM with the partial-data terminal. The full
    set is now: Running plus the Held pause-state plus four
    reachable terminals (Completed, Aborted, Stopped, Truncated).

      Running (6f-1)
        ⇄ Held (6f-3 hold/resume; bidirectional cycle, unlimited)
        → Completed (6f-2 happy-path; single-source from Running)
        → Aborted (6f-2 emergency; multi-source from Running | Held)
        → Stopped (6f-3 controlled exit; multi-source from Running | Held)
        → Truncated (6f-4 partial-data terminal; multi-source from
                     Running | Held)

    Stopped vs Truncated (6f-4 lifecycle-layer distinction):
    Stopped is a controlled exit while the system is responsive and
    the operator decides to end the Run early; data up to the stop
    point is valid. Truncated is a cleanup terminal for a Run that
    became known-dead through interruption (power loss, process
    crash, hardware fault) and is being closed retroactively. The
    Run was already de-facto over before the operator could mark
    it; truncation captures that fact plus the operator's best
    guess at when the actual interruption occurred (optional
    interrupted_at on RunTruncated). The system does not detect
    de-facto-dead Runs itself today (gate-review L4-followup);
    operators must call truncate explicitly.

    Why complete_run is single-source while stop/abort_run are
    multi-source (gate-review 6f-3 Q1 lock): completion claims
    achievement, which requires active work happening at the
    moment of completion. Stop and abort are exits — they don't
    require active work, only any non-terminal state. Operators
    wanting to mark a held run as complete must Resume → Complete,
    which preserves clearer audit semantics than a bare Held →
    Complete transition.

    Plus transient states (Starting, Stopping, Aborting,
    Holding, Unholding, Completing) get evaluated when DAQ-channel
    integration arrives (6f-5+) — only added if there's a real
    async period between command-arrival and event-emit at the
    application layer (today there isn't).

    Naming convention (per 6f-2 gate review): gerund / adjective
    for the active steady-state (matches ISA-88 / PackML's
    `Execute` and Bluesky's `running`); past-participle for
    pause-state and terminals (`Held`, `Completed`, `Aborted`,
    `Stopped`) consistent with our own Subject precedent.

    Enum values are PascalCase strings (matches BC-map status
    vocabulary; log lines and DTOs read naturally without mapping).
    """

    RUNNING = "Running"
    HELD = "Held"
    COMPLETED = "Completed"
    ABORTED = "Aborted"
    STOPPED = "Stopped"
    TRUNCATED = "Truncated"


class InvalidRunNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run name must be 1-{RUN_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class RunAlreadyExistsError(Exception):
    """Attempted to start a run whose stream already has events."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Run {run_id} already exists")
        self.run_id = run_id


class RunNotFoundError(Exception):
    """Attempted an operation on a run whose stream has no events."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Run {run_id} not found")
        self.run_id = run_id


class PlanDeprecatedError(Exception):
    """Attempted to start a Run against a Deprecated Plan.

    Plan deprecation is advisory at the Plan-aggregate layer (Plan
    itself doesn't reject operations on Deprecated state), but
    Run-start rejects — you can't execute a tombstoned Plan.
    Mapped to HTTP 409.

    Symmetric to Plan-bind's PracticeDeprecatedError /
    MethodDeprecatedError pattern from 6e-1.
    """

    def __init__(self, plan_id: UUID) -> None:
        super().__init__(f"Cannot start Run against Plan {plan_id}: Plan is Deprecated")
        self.plan_id = plan_id


class SubjectNotMountableError(Exception):
    """Attempted to start a Run against a Subject not in Mounted | Measured.

    Subject-state precondition for Run-start (gate-review Q6):
    Subject must be in `Mounted` (sample on stage, ready) or
    `Measured` (re-measurement of a previously-measured subject).
    Other states (Received, Removed, Returned, Stored, Discarded)
    don't make sense for a new Run binding.

    Mapped to HTTP 409.
    """

    def __init__(self, subject_id: UUID, current_status: str) -> None:
        super().__init__(
            f"Cannot start Run against Subject {subject_id}: currently in "
            f"status {current_status}, Run-start requires Mounted or Measured"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class RunAssetDecommissionedError(Exception):
    """Plan's bound Assets include one or more Decommissioned at Run-start.

    Re-validation of Asset state at Run-start (NOT just Plan-bind
    snapshot). If an Asset got decommissioned between Plan-bind and
    Run-start, the Run can't proceed against the now-tombstoned
    Asset. Mapped to HTTP 409.

    Mirrors Plan-bind's AssetDecommissionedError shape.
    """

    def __init__(self, asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot start Run: the following Assets bound by the Plan are "
            f"Decommissioned: {[str(a) for a in asset_ids]}"
        )
        self.asset_ids = asset_ids


class RunCapabilitiesNotSatisfiedError(Exception):
    """Plan's Method needs capabilities not currently provided by bound Assets.

    Re-validation at Run-start: the bound Asset capability set
    can drift after Plan-bind (operators add/remove capabilities,
    decommission assets and replace with substitutes, etc.).
    Run-start re-checks the capability superset against current
    Asset state. Mapped to HTTP 409.

    Mirrors Plan-bind's PlanCapabilitiesNotSatisfiedError shape.
    """

    def __init__(self, missing_capability_ids: frozenset[UUID]) -> None:
        super().__init__(
            f"Run capabilities not satisfied at start time: bound Assets "
            f"are missing capabilities "
            f"{sorted(str(c) for c in missing_capability_ids)}"
        )
        self.missing_capability_ids = missing_capability_ids


class RunCannotCompleteError(Exception):
    """Attempted to complete a Run not in `Running`.

    Single-source guard: `complete_run` accepts only `Running`.
    Re-completing an already-`Completed` Run raises (strict-not-
    idempotent); completing an `Aborted` / `Stopped` Run raises;
    completing a `Held` Run raises (gate-review 6f-3 Q1 lock —
    completion claims active achievement, so it requires the Run
    to be actively running; an operator wanting to complete a held
    run must Resume → Complete).

    Per-transition error class — same naming convention as
    `PlanCannotDeprecateError` / `MethodCannotVersionError`.
    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be completed: currently in status "
            f"{current_status.value}, complete requires "
            f"{RunStatus.RUNNING.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotAbortError(Exception):
    """Attempted to abort a Run not in `Running` or `Held`.

    Multi-source guard: `abort_run` accepts `Running | Held`.
    Emergencies during a hold are real — operators can't be
    forced to first resume just to abort. Aborting an already-
    terminal Run (Completed | Aborted | Stopped) raises;
    re-aborting an `Aborted` Run raises (strict-not-idempotent).

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be aborted: currently in status "
            f"{current_status.value}, abort requires "
            f"{RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotHoldError(Exception):
    """Attempted to hold a Run not in `Running`.

    Single-source guard: `hold_run` accepts only `Running`.
    Re-holding an already-`Held` Run raises (strict-not-
    idempotent); holding a terminal Run raises.

    Hold/Resume is bidirectional and unlimited-cycle (PackML +
    Bluesky precedent), so an operator can hold → resume → hold
    repeatedly during a single Run; each hold requires an
    intervening resume.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be held: currently in status "
            f"{current_status.value}, hold requires "
            f"{RunStatus.RUNNING.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotResumeError(Exception):
    """Attempted to resume a Run not in `Held`.

    Single-source guard: `resume_run` accepts only `Held`. The
    inverse of hold (which requires `Running`). Resuming an
    already-`Running` Run raises (strict-not-idempotent);
    resuming a terminal Run raises.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be resumed: currently in status "
            f"{current_status.value}, resume requires "
            f"{RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotStopError(Exception):
    """Attempted to stop a Run not in `Running` or `Held`.

    Multi-source guard: `stop_run` accepts `Running | Held`.
    Symmetric with abort_run's source set, operator-initiated
    controlled exits don't require an active state, only any
    non-terminal state. Stopping a terminal Run raises.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be stopped: currently in status "
            f"{current_status.value}, stop requires "
            f"{RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotTruncateError(Exception):
    """Attempted to truncate a Run not in `Running` or `Held`.

    Multi-source guard: `truncate_run` accepts `Running | Held`.
    Same source set as stop / abort, every operator-initiated
    terminal accepts any non-terminal state. Truncating a Run that
    has already reached a terminal (Completed | Aborted | Stopped |
    Truncated) raises; re-truncating a `Truncated` Run raises
    (strict-not-idempotent, matches the other terminals).

    Truncated and Stopped are both operator-initiated, but they are
    semantically distinct: Stopped is a controlled exit while the
    system is still responsive; Truncated is the cleanup mechanism
    for a Run that became de-facto dead through interruption (power
    loss, process crash, hardware fault) and is being closed
    retroactively. The current_status field will typically still be
    Running (the FSM never observed the interruption) when
    truncate is called.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be truncated: currently in status "
            f"{current_status.value}, truncate requires "
            f"{RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class InvalidRunAbortReasonError(ValueError):
    """The supplied abort reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    `InvalidPlanVersionTagError` / `InvalidPracticeVersionTagError`.

    Free-form `str` (1-500 chars) is the locked 6f-2 design (gate-
    review Q2). Structured taxonomy is future-additive when the
    documented re-evaluation triggers fire:
      - vocabulary convergence across ≥10 real aborts;
      - Decision BC adopts RunAbort with structured-context queries;
      - compliance/audit demand for categorical reason tracking.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run abort reason must be 1-{RUN_ABORT_REASON_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class RunAbortReason:
    """Free-form abort reason. Trimmed; 1-500 chars.

    Domain VO (not just `str`) so the decider validates uniformly
    via the shared `validate_name` helper (same trimming + bounded-
    length contract as the 11 BoundedName VOs). The on-the-wire
    representation in `RunAborted.reason` is `str` (post-trim) for
    payload simplicity; the VO exists at decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=RUN_ABORT_REASON_MAX_LENGTH,
            error_class=InvalidRunAbortReasonError,
        )
        object.__setattr__(self, "value", trimmed)


class InvalidRunStopReasonError(ValueError):
    """The supplied stop reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Sibling of
    `InvalidRunAbortReasonError`; kept as a separate class so API
    error responses unambiguously identify which transition the
    invalid reason was for.

    Free-form `str` (1-500 chars) is the locked 6f-3 design (gate-
    review Q2). Same future-additive structured-taxonomy posture
    as `RunAborted.reason` — the three documented re-evaluation
    triggers for abort apply equally to stop:
      - vocabulary convergence across ≥10 real stops;
      - Decision BC adopts RunStop with structured-context queries;
      - compliance/audit demand for categorical reason tracking.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run stop reason must be 1-{RUN_STOP_REASON_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class RunStopReason:
    """Free-form stop reason. Trimmed; 1-500 chars.

    Sibling of `RunAbortReason`, identical pattern, distinct
    error class for clearer API error responses. The on-the-wire
    representation in `RunStopped.reason` is `str` (post-trim)
    for payload simplicity; the VO exists at decider-input time
    only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=RUN_STOP_REASON_MAX_LENGTH,
            error_class=InvalidRunStopReasonError,
        )
        object.__setattr__(self, "value", trimmed)


class InvalidRunTruncateReasonError(ValueError):
    """The supplied truncate reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Sibling of
    `InvalidRunStopReasonError`; kept as a separate class so API
    error responses unambiguously identify which transition the
    invalid reason was for.

    Free-form `str` (1-500 chars) is the locked 6f-4 design (gate-
    review L8 + stress-test confirmation). Same future-additive
    structured-taxonomy posture as `RunAborted.reason` /
    `RunStopped.reason`, the same three documented re-evaluation
    triggers apply:
      - vocabulary convergence across >=10 real truncations;
      - Decision BC adopts RunTruncate with structured-context queries;
      - compliance/audit demand for categorical reason tracking.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run truncate reason must be 1-{RUN_TRUNCATE_REASON_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class InvalidRunInterruptedAtError(ValueError):
    """The supplied truncate `interrupted_at` is in the future relative to `now`.

    `interrupted_at` is the operator's best guess at when the
    actual interruption happened, separate from `occurred_at`
    (when the truncate command was processed). The two timestamps
    can be hours or days apart for weekend / overnight
    interruptions, but `interrupted_at` MUST not be later than
    `now`, you cannot have been interrupted in the future.

    Validated defensively at the decider via this error so direct
    in-process callers (sagas, tests) get the same protection as
    HTTP / MCP callers. The API surface does not pre-validate
    against `now` (Pydantic Field has no relative-bound primitive),
    only the absolute schema (datetime parse + tz-aware), so this
    decider check is the one source of truth.

    Mapped to HTTP 400.
    """

    def __init__(self, interrupted_at: datetime, now: datetime) -> None:
        super().__init__(
            f"Run truncate interrupted_at {interrupted_at.isoformat()} is in the future "
            f"(now is {now.isoformat()}); the interruption cannot have happened later than "
            f"the truncate command itself"
        )
        self.interrupted_at = interrupted_at
        self.now = now


@dataclass(frozen=True)
class RunTruncateReason:
    """Free-form truncate reason. Trimmed; 1-500 chars.

    Sibling of `RunStopReason` and `RunAbortReason`. The on-the-
    wire representation in `RunTruncated.reason` is `str` (post-
    trim); the VO exists at decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=RUN_TRUNCATE_REASON_MAX_LENGTH,
            error_class=InvalidRunTruncateReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class RunName:
    """Display name for a run. Trimmed; 1-200 chars.

    Eleventh occurrence of the trimmed-bounded-name VO pattern.
    Uses the shared `validate_name` helper hoisted in 6e-1 (see
    `cora.infrastructure.name`).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=RUN_NAME_MAX_LENGTH,
            error_class=InvalidRunNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Run:
    """Aggregate root: one execution instance.

    `plan_id` is the Plan being executed (eventual-consistency ref;
    loaded at handler-load time for re-validation, NOT verified by
    the decider as opaque). `subject_id` is the Subject being
    measured, or None for calibration / dark-field runs. `raid` is
    the Research Activity Identifier (ISO 23527) for the project
    this Run belongs to, opaque string carried verbatim, defaults
    to None (post-7d retrofit; pre-7d Runs fold with raid=None
    because old RunStarted payloads have no raid key). `status`
    defaults to `Running` — the active steady-state.

    `parameter_overrides` (post-6g-c) is the operator-supplied
    overrides on top of `Plan.parameter_defaults` (RFC 7396 merge).
    `effective_parameters` is the post-merge resolved snapshot
    (defaults + overrides) that governed this Run. Both default to
    `{}` for legacy pre-6g-c streams (additive-state pattern;
    forward-compat via `payload.get(..., {})` in `from_stored`).
    Mirrors Bluesky start-document / MLflow run.params / W&B
    run.config / ISA-88 control-recipe / RO-Crate CreateAction
    convention: the run carries the resolved parameter set as a
    first-class read surface (researched 2026-05-14;
    [[project_run_parameters_design]] §6g-c).

    `triggered_by` (post-6g-c) is operator-supplied free text
    capturing what initiated this Run (operator-manual, scheduler,
    prior-run, automation). Optional. Future Decision-BC integration
    may populate this from `DecisionReasoning.entries` references.
    """

    id: UUID
    name: RunName
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None = None
    status: RunStatus = RunStatus.RUNNING
    parameter_overrides: dict[str, Any] = field(default_factory=dict[str, Any])
    effective_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    triggered_by: str | None = None


class InvalidRunParametersError(ValueError):
    """The supplied Run effective_parameters (defaults + overrides) failed
    validation against the owning Method's parameters_schema (Phase 6g-c).

    Permissive when Method.parameters_schema is None: any merge result
    is accepted (Method declares no contract). When the schema IS
    declared, the merged dict must conform per jsonschema-rs Draft
    2020-12. Mirrors `InvalidPlanParameterDefaultsError` shape from
    6g-b. Mapped to HTTP 400 by the run BC's exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Run parameters: {reason}")
        self.reason = reason
