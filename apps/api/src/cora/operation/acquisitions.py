"""Substrate-neutral data-acquisition action bodies for the Conductor.

The three primitives `collect` / `discrete` / `continuous` register as
named `ActionBody` callables in the `InMemoryActionRegistry` the
`Conductor` consumes. `collect` is the single-detector capture cycle;
`discrete` and `continuous` compose it for trajectory + fly-scan use.

See `project_scan_primitives_design` for the design lock and
`project_scan_primitives_research` for the corpus that backs the
substrate-neutral parameter shapes.

## v1 contract: areaDetector ADCore PV convention

`collect` integrates with areaDetector's ADCore PV layout. `params.detector`
is the areaDetector root prefix (e.g., `"2bma:cam1"`); the body writes
to sibling PVs:

  - `{detector}:TriggerMode` <- mapped from `trigger_mode`
  - `{detector}:AcquireTime` <- `dwell` (seconds)
  - `{detector}:NumImages`   <- `repetitions` (or `0` for free-run)
  - `{detector}:Acquire`     <- `1` to start
  - `{detector}:Acquire_RBV` -> polled until `0` / `"Done"`
  - `{detector}:DetectorState_RBV` -> read once for final-state evidence

Trigger-mode value mapping translates the substrate-neutral primitive
vocabulary into AD-coded strings: `ExternalEdge` and `ExternalLevel`
both collapse to AD's `"External"`; edge polarity vs level is carried
on the trigger EMITTER (PandABox PCOMP, Aerotech PSO, etc.), not the
detector. Non-AD detectors will land as their own action bodies; promote
a shared shape when 3 detector families exist (rule-of-three).

## v1 detector-side / emitter-side split

`collect` writes ONLY the detector-side trigger PVs. The `polarity` and
`source` fields are validated by Pydantic and recorded in the returned
evidence mapping, but they are NOT written to PVs by `collect`. The
trigger EMITTER (the device named by `source`) is configured by the
caller via setpoint steps that precede the action step in the Procedure,
or by a future Capability template that expands trigger configuration
into the step list. This split keeps the primitive substrate-neutral on
the emitter side, where addressing conventions vary by hardware (PCOMP
PV layout differs from PSO PV layout differs from software clock).
Revisit at first PandABox-or-Aerotech integration.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cora.operation.conductor import ActionContext


_AD_TRIGGER_MODE_VALUES: Mapping[str, str] = {
    "Internal": "Internal",
    "ExternalEdge": "External",
    "ExternalLevel": "External",
}
"""Substrate-neutral trigger_mode value -> areaDetector ADCore string.

AD collapses edge vs level into one `"External"` value; the
distinction is carried at the trigger emitter, not the detector."""


_POLL_INTERVAL_S: float = 0.05
"""Poll period between Acquire_RBV reads inside `collect`'s done-loop.

50ms balances responsiveness against unnecessary CA / PVA traffic for
the typical sub-second to multi-second acquisition durations. The body
relies on caller-side cancellation (Procedure abort) for hard timeout;
no internal bound is enforced at v1."""


class CollectParams(BaseModel):
    """Validated parameters for the `collect` action body.

    Substrate-neutral field shape per [[project_scan_primitives_design]].
    The `@model_validator` enforces the three conditional rules that the
    JSON-Schema subset cannot express today (per design memo Watch item 3):

      - `polarity` is required iff `trigger_mode == "ExternalEdge"`
      - `source` is required when `trigger_mode != "Internal"`
      - `source` must be `None` when `trigger_mode == "Internal"`

    `dwell` carries the canonical `unit: {system, code}` annotation per
    [[project_units_design]] (no `_seconds` suffix). `repetitions` has a
    `ge=1` floor; `0` collides with the AD `NumImages=0` continuous
    sentinel, so `None` is the only way to request free-run.
    """

    detector: str
    trigger_mode: Literal["Internal", "ExternalEdge", "ExternalLevel"]
    polarity: Literal["Rising", "Falling", "Either"] | None = None
    source: str | None = None
    repetitions: int | None = Field(default=None, ge=1)
    dwell: float = Field(
        ...,
        gt=0,
        json_schema_extra={"unit": {"system": "udunits", "code": "s"}},
    )

    @model_validator(mode="after")
    def _check_trigger_constraints(self) -> CollectParams:
        if self.trigger_mode == "ExternalEdge" and self.polarity is None:
            raise ValueError("polarity required when trigger_mode == ExternalEdge")
        if self.trigger_mode != "Internal" and self.source is None:
            raise ValueError("source required when trigger_mode != Internal")
        if self.trigger_mode == "Internal" and self.source is not None:
            raise ValueError("source must be None when trigger_mode == Internal")
        return self


async def collect(ctx: ActionContext) -> Mapping[str, Any]:
    """Single-detector capture against areaDetector ADCore PV convention.

    Writes TriggerMode / AcquireTime / NumImages, starts Acquire, polls
    Acquire_RBV until `0` / `"Done"`, reads DetectorState_RBV for the
    final-state evidence, returns a Mapping the Conductor records as the
    step entry's `result_data`.

    `Control*Error` raised by the underlying `ControlPort` propagates
    unchanged; the Conductor catches it at the action-dispatch site and
    records the step failure per its standard contract.

    See module docstring for the AD-convention v1 contract and the
    detector-side / emitter-side split that leaves `polarity` and
    `source` as evidence-only fields (the trigger EMITTER is configured
    by caller-authored setpoint steps before this action step).
    """
    params = CollectParams.model_validate(ctx.params)
    started_at = ctx.clock.now()

    await ctx.control_port.write(
        f"{params.detector}:TriggerMode",
        _AD_TRIGGER_MODE_VALUES[params.trigger_mode],
    )
    await ctx.control_port.write(f"{params.detector}:AcquireTime", params.dwell)
    await ctx.control_port.write(
        f"{params.detector}:NumImages",
        params.repetitions if params.repetitions is not None else 0,
    )
    await ctx.control_port.write(f"{params.detector}:Acquire", 1)

    while True:
        reading = await ctx.control_port.read(f"{params.detector}:Acquire_RBV")
        if reading.value in (0, "Done"):
            break
        await asyncio.sleep(_POLL_INTERVAL_S)

    stopped_at = ctx.clock.now()
    state_reading = await ctx.control_port.read(f"{params.detector}:DetectorState_RBV")

    return {
        "started_at": started_at.isoformat(),
        "stopped_at": stopped_at.isoformat(),
        "repetitions_requested": params.repetitions,
        "trigger_mode": params.trigger_mode,
        "polarity": params.polarity,
        "source": params.source,
        "detector_state_final": state_reading.value,
    }


__all__ = ["CollectParams", "collect"]
