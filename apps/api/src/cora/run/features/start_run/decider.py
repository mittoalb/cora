"""Pure decider for the `StartRun` command.

Cross-aggregate validation: this is the second decider in the
codebase that takes upstream aggregate state as input (after Plan's
`define_plan` from 6e-1). Per gate-review Q2, the handler pre-loads
Plan + Subject (if subject_id given) + each bound Asset, hands the
loaded entities to this decider as a `RunStartContext`. The decider
treats them as opaque domain data and validates without any I/O.
`now` and `new_id` are injected by the handler from Clock and
IdGenerator ports.

This pattern is the canonical approach for cross-aggregate
validation in CORA going forward (Plan was first, Run is second).
Documented in CONTRIBUTING.md alongside the eventual-consistency
rule.

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most
fundamental issues surface first:

1. State must be None (defensive: stream collision).
   `RunAlreadyExistsError`.
2. Plan must not be Deprecated → `PlanDeprecatedError`.
3. Subject (if non-None) must be in {Mounted, Measured} →
   `SubjectNotMountableError`. Skipped entirely for calibration /
   dark-field runs (where command.subject_id is None and
   context.subject is None).
4. No bound Asset may be Decommissioned → `RunAssetDecommissionedError`
   carrying the offending asset_ids.
5. RE-VALIDATE: `union(asset.capabilities) ⊇ method.needs_capabilities`
   against CURRENT Asset state (gate-review Q5: drift since Plan-bind
   is real; Run-start is the last gate before execution).
   `RunCapabilitiesNotSatisfiedError` carrying the missing capability
   ids. **NOTE**: Method's needs_capabilities comes via Plan; we
   load Plan but NOT Method here — instead, the handler resolved
   Plan → Method at load time and passes the needs as part of...
   wait, re-reading: actually we don't have Method directly in
   RunStartContext. Plan's bind-time snapshot in PlanDefined event
   carries `method_needs_capabilities_snapshot`, but we need
   CURRENT Method state for re-validation. The handler must load
   Method via plan.practice_id → practice.method_id → Method.
   See handler docstring.

   Wait, simpler: we re-load via the snapshot. The PlanDefined
   event captured method_id and the needs snapshot. We could trust
   the snapshot, OR we could re-load Method to get current
   needs_capabilities. Per gate-review Q5 ("re-validate at Run-
   start"), we re-load to catch Method drift too.

   Actually for 6f-1 simplicity, we trust Plan's bind-time
   snapshot for the needs side AND re-validate against current
   Asset capabilities. Method drift between bind and start is a
   secondary concern; if Method's needs change, operators should
   re-bind the Plan. Documented as known gap.

6. Name validation (via `RunName` VO). `InvalidRunNameError`. Last
   because the name is a primitive the operator can fix without
   changing any binding state.

## What's NOT validated

  - Supply availability (Track B Supply BC not shipped). Documented
    as gate-review Q3 known gap.
  - Decision approval (Decision BC not shipped). Documented as
    gate-review Q3 known gap.
  - Subject hazard ⊆ Method clearances (Method's hazardClearances
    facet not shipped). Documented as 6c-deferred enrichment.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from cora.equipment.aggregates.asset import AssetLifecycle
from cora.recipe.aggregates.plan import PlanStatus
from cora.run.aggregates.run import (
    PlanDeprecatedError,
    Run,
    RunAlreadyExistsError,
    RunAssetDecommissionedError,
    RunCapabilitiesNotSatisfiedError,
    RunName,
    RunStarted,
    SubjectNotMountableError,
    validate_effective_parameters_against_method_schema,
)
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.context import RunStartContext
from cora.subject.aggregates.subject import SubjectStatus

_SUBJECT_RUNNABLE_STATUSES: tuple[SubjectStatus, ...] = (
    SubjectStatus.MOUNTED,
    SubjectStatus.MEASURED,
)


def decide(
    state: Run | None,
    command: StartRun,
    *,
    context: RunStartContext,
    needs_capabilities_snapshot: frozenset[UUID],
    effective_parameters: dict[str, Any],
    method_parameters_schema: dict[str, Any] | None,
    now: datetime,
    new_id: UUID,
) -> list[RunStarted]:
    """Decide the events produced by starting a new run.

    `needs_capabilities_snapshot` is the Method's needs_capabilities
    set the handler resolved transitively from `plan.practice_id →
    practice.method_id → method.needs_capabilities`. Passed in as a
    plain frozenset so the decider stays purely state-driven.

    `effective_parameters` is the post-merge dict (Plan defaults +
    command overrides) the handler computed via `merge_patch`.
    `method_parameters_schema` is the Method's parameters_schema
    (None if Method declares no contract). The decider validates
    `effective_parameters` against the schema (permissive when the
    schema is None per 6g-b posture) and emits RunStarted carrying
    BOTH the operator's overrides AND the resolved effective set.
    """
    if state is not None:
        raise RunAlreadyExistsError(state.id)

    if context.plan.status is PlanStatus.DEPRECATED:
        raise PlanDeprecatedError(context.plan.id)

    if context.subject is not None and context.subject.status not in _SUBJECT_RUNNABLE_STATUSES:
        raise SubjectNotMountableError(
            context.subject.id, current_status=context.subject.status.value
        )

    decommissioned = sorted(
        (
            asset.id
            for asset in context.assets.values()
            if asset.lifecycle is AssetLifecycle.DECOMMISSIONED
        ),
        key=str,
    )
    if decommissioned:
        raise RunAssetDecommissionedError(decommissioned)

    # Re-validation: union of CURRENT bound Asset capabilities must
    # cover Method's needs (per gate-review Q5; drift since Plan-bind
    # is real; Run-start is the last gate).
    union_capabilities: frozenset[UUID] = frozenset(
        cap for asset in context.assets.values() for cap in asset.capabilities
    )
    missing = needs_capabilities_snapshot - union_capabilities
    if missing:
        raise RunCapabilitiesNotSatisfiedError(missing)

    # 6g-c: validate the resolved (defaults + overrides) parameter set
    # against the owning Method's parameters_schema. Permissive when
    # the schema is None (Method declares no contract — accept any
    # merge result; locked posture per [[project_run_parameters_design]]).
    validate_effective_parameters_against_method_schema(
        effective_parameters, method_parameters_schema
    )

    name = RunName(command.name)  # validates + trims; raises InvalidRunNameError
    return [
        RunStarted(
            run_id=new_id,
            name=name.value,
            plan_id=command.plan_id,
            subject_id=command.subject_id,
            raid=command.raid,
            parameter_overrides=command.parameter_overrides,
            effective_parameters=effective_parameters,
            triggered_by=command.triggered_by,
            occurred_at=now,
        )
    ]
