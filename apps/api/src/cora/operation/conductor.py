"""Operation BC `Conductor`: walks setpoint steps via ControlPort, records to logbook.

The Conductor is the Operation BC's Layer-2 runtime per
[[project_edge_runtime_design]]. It receives a sequence of setpoint
operations, dispatches each through the Stage-1 `ControlPort` family
(`InMemoryControlPort` / `CaprotoControlPort` / `EpicsCaControlPort`
/ `EpicsPvaControlPort` / `ControlPortRegistry`), and records every
outcome as a `step_kind="setpoint"` entry in the Procedure's steps
logbook via the existing `append_procedure_step` handler.

The Conductor is a single-process asyncio walker; per-call state
lives on the returned `ConductorResult`. Substrate-agnostic: the
`address` string parses substrate-specific syntax inside the routed
adapter; the Conductor never branches on substrate.

## Failure mode

The first step that raises any `Control*Error` halts execution. The
failing step IS recorded in the logbook (payload's `result="failed"`
+ `error_class` + `message`) before the call returns; subsequent
steps are NOT attempted. The Procedure's FSM is NOT advanced by the
Conductor; the caller decides abort vs retry vs hand-off after
inspecting `ConductorResult.failure`.

## Out of scope at this iteration

The minimal sketch covers setpoint only. The following land in
subsequent iterations of the Stage-2 arc:

  - `action` step kind (callable from a registered action body)
  - `check` step kind (post-condition verification via `ControlPort.read`)
  - pre/post setpoint evidence-capture readings
  - FSM transition wiring (`start_procedure` -> execute -> `complete_procedure`)
  - cancellation mid-execute (via `asyncio.CancelledError` propagation)
  - concurrent / pipelined setpoint dispatch (sequential at v1)
  - `Capability`-driven step-list resolution (caller supplies the list)

These are intentional deferrals to keep the Stage-2 sketch reviewable
without committing to a runtime architecture that has not yet earned
its keep against pilot pressure.

## Why call the handler not the store directly

`append_procedure_step` is the slice handler that owns lazy-open of
the steps logbook + status guard (Procedure must be `Running`) +
authorization. The Conductor calls the handler, not the underlying
`StepStore`, so those concerns stay caged inside the existing slice
and the Conductor stays a thin orchestrator. The dependency is the
handler's `Handler` Protocol, not a concrete binding, so tests inject
a fake without standing up the full handler machinery.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.infrastructure.ports.clock import Clock
from cora.infrastructure.ports.id_generator import IdGenerator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.features.append_procedure_step.command import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from cora.operation.features.append_procedure_step.handler import (
    Handler as AppendProcedureStepHandler,
)
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlPort,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
)

_CONTROL_ERRORS: tuple[type[Exception], ...] = (
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlWriteRejectedError,
    ControlValueCoercionError,
    ControlAccessDeniedError,
)
"""The closed set of `Control*Error` classes the Conductor maps to
`ConductorFailure`. Tuple shape lets the `except` clause stay
declarative; new exception classes in `cora.operation.ports.control_port`
must be added here explicitly (no `Exception` catch-all so non-port
exceptions still propagate to the caller's task)."""


_STEP_KIND_SETPOINT = "setpoint"
_RESULT_OK = "ok"
_RESULT_FAILED = "failed"
"""Payload constants. `step_kind` is the closed-set discriminator from
[[project_operation_design]] (`setpoint | action | check`). `result`
is a Conductor-local convention inside the setpoint payload body; the
discriminator is unused by today's projections but pinned so future
read-side filters can split successful vs failed setpoints without
parsing the message string."""


@dataclass(frozen=True)
class SetpointStep:
    """One setpoint operation: write `value` to `address`.

    `address` is a substrate-agnostic string per
    [[project_control_port_design]]. The routed `ControlPort` adapter
    parses substrate-specific syntax (EPICS PV name, Tango TRL, OPC
    UA NodeId) so the Conductor never branches on substrate.
    """

    address: str
    value: int | float | bool | str | tuple[Any, ...]


@dataclass(frozen=True)
class ConductorFailure:
    """First step that raised a `Control*Error`; the Conductor halts here.

    `error_class` is the simple class name (no module prefix); the
    `message` carries the formatted `str(exc)` output. Both land in
    the recorded step payload so log inspection from the read-side
    matches what's on the `ConductorResult`.
    """

    step_index: int
    address: str
    error_class: str
    message: str


@dataclass(frozen=True)
class ConductorResult:
    """Outcome of a `Conductor.execute_setpoints` call.

    `completed_count` is the number of setpoint steps that fully
    wrote AND recorded a success entry. The failing step (if any) is
    NOT counted in `completed_count`; its failure is recorded in the
    logbook AND surfaced in `failure`.
    """

    procedure_id: UUID
    completed_count: int
    failure: ConductorFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


class Conductor:
    """Operation BC Layer-2 runtime: walks setpoint steps via ControlPort.

    Stateless walker. Construct once at app wire-up time; call
    `execute_setpoints` per Procedure execution. Per-call state lives
    on the returned `ConductorResult`.

    The Conductor calls the `append_procedure_step` handler (not the
    underlying `StepStore`) so lazy-open + status guard + authorization
    stay inside that slice. See module docstring for failure mode +
    out-of-scope.
    """

    def __init__(
        self,
        *,
        control_port: ControlPort,
        append_step: AppendProcedureStepHandler,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._control_port = control_port
        self._append_step = append_step
        self._clock = clock
        self._id_generator = id_generator

    async def execute_setpoints(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[SetpointStep],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Walk `steps` in order; write each via ControlPort + record outcome.

        Halts on the first `Control*Error`. The failing step is
        recorded in the logbook (`result="failed"`) BEFORE this
        returns; subsequent steps are NOT attempted. The Procedure's
        FSM is unchanged.

        Non-port exceptions (programmer errors, KeyboardInterrupt,
        CancelledError) are NOT caught: they propagate to the caller
        so signals + cancellation behave normally and bugs surface.
        """
        completed = 0
        for index, step in enumerate(steps):
            try:
                await self._control_port.write(step.address, step.value, wait=True)
            except _CONTROL_ERRORS as exc:
                await self._record(
                    procedure_id=procedure_id,
                    principal_id=principal_id,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    surface_id=surface_id,
                    step=step,
                    result=_RESULT_FAILED,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=completed,
                    failure=ConductorFailure(
                        step_index=index,
                        address=step.address,
                        error_class=type(exc).__name__,
                        message=str(exc),
                    ),
                )
            await self._record(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
                step=step,
                result=_RESULT_OK,
            )
            completed += 1
        return ConductorResult(procedure_id=procedure_id, completed_count=completed)

    async def _record(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        surface_id: UUID,
        step: SetpointStep,
        result: str,
        error_class: str | None = None,
        message: str | None = None,
    ) -> None:
        """Append a single setpoint step entry via the injected handler.

        The payload carries the address + value the Conductor attempted
        plus `result` (and `error_class` + `message` on failure). The
        body shape is Conductor-local: future Stage-2 iterations may
        extend it (pre/post readings, retry counts, etc.) additively.
        """
        payload: dict[str, Any] = {
            "address": step.address,
            "value": step.value,
            "result": result,
        }
        if error_class is not None:
            payload["error_class"] = error_class
        if message is not None:
            payload["message"] = message
        sampled_at = self._clock.now()
        entry = ProcedureStepInput(
            event_id=self._id_generator.new_id(),
            step_kind=_STEP_KIND_SETPOINT,
            payload=payload,
            sampled_at=sampled_at,
            occurred_at=sampled_at,
        )
        await self._append_step(
            AppendProcedureSteps(procedure_id=procedure_id, entries=(entry,)),
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )


__all__ = [
    "Conductor",
    "ConductorFailure",
    "ConductorResult",
    "SetpointStep",
]
