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
  - `status: RunStatus` (`Started` only at 6f-1; transitions in
    6f-2+)

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

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.name import validate_name

RUN_NAME_MAX_LENGTH = 200


class RunStatus(StrEnum):
    """The Run's lifecycle state.

    6f-1 ships only `Started`. Transitions land per-slice in
    6f-2+ per the BC map's full FSM:

      Started (6f-1)
        → Completed | Aborted (6f-2 happy + emergency exit)
        → Held (6f-3 hold/resume)
        → Stopped (6f-3 controlled stop)
        → Truncated (6f-4 partial-data terminal)

    Plus transient states (Starting, Running, Stopping, Aborting,
    Completing) get evaluated in 6f-2 — only added if Run handlers
    actually do async work between command-arrival and event-emit.

    Enum values are PascalCase strings (matches BC-map status
    vocabulary; log lines and DTOs read naturally without mapping).
    """

    STARTED = "Started"


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
    measured, or None for calibration / dark-field runs. `status`
    defaults to `Started` (6f-1 ships only this state).
    """

    id: UUID
    name: RunName
    plan_id: UUID
    subject_id: UUID | None
    status: RunStatus = RunStatus.STARTED
