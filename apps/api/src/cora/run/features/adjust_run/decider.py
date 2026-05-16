"""Pure decider for the `AdjustRun` command (Phase 6j).

Mid-flight parameter steering: an in-progress Run keeps its identity
+ Subject + Plan + Method + Asset binding + Campaign membership +
FSM continuity while recording a parameter mutation as an additive
event on the Run's stream. Source-state guard `{Running, Held}`
(Idle/Starting use `override_parameters` at start_run; terminal
states are by definition frozen).

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most fundamental
issues surface first:

  1. State must not be None -> `RunNotFoundError` (reused from Run BC).
  2. State.status must be in `_ADJUSTABLE_STATUSES` (RUNNING | HELD)
     -> `RunCannotAdjustError(run_id, current_status)`.
  3. `parameter_patch` must be non-empty (len > 0)
     -> `InvalidRunAdjustmentPatchError("must contain at least one change")`.
  4. `reason` length 1-500 chars after trim
     -> `InvalidRunAdjustReasonError`.
  5. Compute `merged = merge_patch(state.effective_parameters, patch)`;
     when `context.method_parameters_schema is not None`, validate
     `merged` against the schema (STRICT-by-default per the 5g-c
     anchor; schemaless Methods skip validation).
     -> `InvalidRunAdjustmentSchemaError(detail)` on violation.
  6. Emit `RunAdjusted(run_id, parameter_patch, effective_parameters=merged,
     reason=trimmed, decided_by_decision_id, occurred_at=now)`.

The merged effective set is emitted on the payload (alongside the
patch) so projections / read endpoints don't need to fold prior
RunAdjusted events to surface the current value. Mirrors
`RunStarted.effective_parameters` snapshot precedent.

`decided_by_decision_id` flows through to the event payload
verbatim. NOT verified at decider (eventual-consistency stance per
Trust.Conduit / Asset parent / Procedure target / Campaign
lead_actor / Run.subject_id precedent).
"""

from datetime import datetime
from typing import Any

import jsonschema_rs

from cora.infrastructure.json_merge_patch import merge_patch
from cora.run.aggregates.run import (
    RUN_ADJUST_REASON_MAX_LENGTH,
    InvalidRunAdjustmentPatchError,
    InvalidRunAdjustmentSchemaError,
    InvalidRunAdjustReasonError,
    Run,
    RunAdjusted,
    RunCannotAdjustError,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features.adjust_run.command import AdjustRun
from cora.run.features.adjust_run.context import RunAdjustContext

_ADJUSTABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)


def _validate_reason(value: str) -> str:
    """Trim + bound-check the operator-supplied reason.

    Mirrors the `validate_bounded_text` shape but raises the
    adjust-specific error class for unambiguous API responses.
    """
    trimmed = value.strip()
    if not trimmed or len(trimmed) > RUN_ADJUST_REASON_MAX_LENGTH:
        raise InvalidRunAdjustReasonError(value)
    return trimmed


def _validate_merged_against_schema(
    merged: dict[str, Any],
    schema: dict[str, Any] | None,
) -> None:
    """Strict-when-schema-present validation of the post-merge dict.

    `adjust_run` deliberately uses a different posture from
    `start_run` (6g-c) for the schemaless-Method case: an adjustment
    on a schemaless Method is operator-responsibility territory
    (the steering operator is iterating intentionally outside a
    declared contract). When the Method has no schema, no validation
    runs. When the Method declares a schema, the merged dict must
    conform; otherwise raise `InvalidRunAdjustmentSchemaError`.
    """
    if schema is None:
        return
    if not merged:
        # Trivial: empty merged set always conforms (required-field
        # checks apply at Run-start, not at each adjustment).
        return
    try:
        validator = jsonschema_rs.Draft202012Validator(schema)  # type: ignore[no-untyped-call]
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        raise InvalidRunAdjustmentSchemaError(
            f"jsonschema-rs failed to compile the schema: {exc}"
        ) from exc

    errors = list(validator.iter_errors(merged))  # type: ignore[no-untyped-call]
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.instance_path) or "<root>"  # type: ignore[union-attr]
        raise InvalidRunAdjustmentSchemaError(
            f"validation failed at {path}: {first.message}"  # type: ignore[union-attr]
        )


def decide(
    state: Run | None,
    command: AdjustRun,
    *,
    context: RunAdjustContext,
    now: datetime,
) -> list[RunAdjusted]:
    """Decide the events produced by adjusting an in-progress Run.

    `state` is the source-state Run (None means the Run has no stream;
    raises `RunNotFoundError`). `context.method_parameters_schema` is
    the Method's optional schema (None means schemaless Method;
    validation skipped). `now` is the wall clock from the handler
    (injected per non-determinism principle).
    """
    if state is None:
        raise RunNotFoundError(command.run_id)

    if state.status not in _ADJUSTABLE_STATUSES:
        raise RunCannotAdjustError(state.id, current_status=state.status)

    if not command.parameter_patch:
        raise InvalidRunAdjustmentPatchError("must contain at least one change")

    trimmed_reason = _validate_reason(command.reason)

    merged = merge_patch(state.effective_parameters, command.parameter_patch)
    _validate_merged_against_schema(merged, context.method_parameters_schema)

    return [
        RunAdjusted(
            run_id=state.id,
            parameter_patch=command.parameter_patch,
            effective_parameters=merged,
            reason=trimmed_reason,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )
    ]
