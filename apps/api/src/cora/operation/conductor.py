"""Operation BC `Conductor`: walks Procedure steps via ControlPort + actions.

The Conductor is the Operation BC's Layer-2 runtime per
[[project_edge_runtime_design]]. It receives a sequence of `Step`
operations (a discriminated union over `SetpointStep | ActionStep`),
dispatches each through the right primitive (`ControlPort.write` for
setpoints, an action body looked up in the `ActionRegistry` for
actions), and records every outcome as a step entry in the
Procedure's steps logbook via the existing `append_procedure_step`
handler.

The Conductor is a single-process asyncio walker; per-call state
lives on the returned `ConductorResult`. Substrate-agnostic on the
setpoint path (address parses inside the routed `ControlPort`
adapter); body-agnostic on the action path (the registry maps a
free-form name to a callable the deployment supplies).

## Failure mode

The first step that raises any `Control*Error` OR the first action
whose name is not registered halts execution. The failing step IS
recorded in the logbook (payload's `result="failed"` + `error_class`
+ `message`) before the call returns; subsequent steps are NOT
attempted. The Procedure's FSM is NOT advanced by the Conductor;
the caller decides abort vs retry vs hand-off after inspecting
`ConductorResult.failure`.

Non-`Control*Error` exceptions raised by an action body (programmer
errors, `KeyboardInterrupt`, `CancelledError`, third-party-library
crashes) are NOT caught: they propagate to the caller so signals +
cancellation behave normally and bugs surface. Action bodies that
want to signal a domain-level "this didn't work out" without throwing
can return a result dict carrying their own status (e.g. `{"ok":
False, "reason": "out_of_range"}`); the Conductor treats any return
from a body as success-shaped at this tier.

## Out of scope at this iteration

The Stage-2 arc continues. The following land in subsequent iters:

  - `check` step kind (post-condition verification via `ControlPort.read`)
  - pre/post setpoint evidence-capture readings
  - FSM transition wiring (`start_procedure` -> execute -> `complete_procedure`)
  - cancellation mid-execute (today CancelledError propagates uncaught)
  - concurrent / pipelined setpoint dispatch (sequential at v1)
  - `Capability`-driven step-list resolution (caller supplies the list)
  - action-body discovery from disk / config (registry is hand-built today)

## Why call the handler not the store directly

`append_procedure_step` is the slice handler that owns lazy-open of
the steps logbook + status guard (Procedure must be `Running`) +
authorization. The Conductor calls the handler, not the underlying
`StepStore`, so those concerns stay caged inside the existing slice
and the Conductor stays a thin orchestrator. The dependency is the
handler's `Handler` Protocol, not a concrete binding, so tests inject
a fake without standing up the full handler machinery.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.ports.clock import Clock
from cora.infrastructure.ports.id_generator import IdGenerator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.errors import UnknownActionError
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
_STEP_KIND_ACTION = "action"
_RESULT_OK = "ok"
_RESULT_FAILED = "failed"
"""Payload constants. `step_kind` is the closed-set discriminator from
[[project_operation_design]] (`setpoint | action | check`). `result`
is a Conductor-local convention inside the step payload body; today's
projections do not split on it, but the field is pinned so future
read-side filters can separate successful vs failed steps without
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
class ActionStep:
    """One action invocation: look up `name` in the registry, run with `params`.

    Action bodies are deployment-supplied callables that compose
    `ControlPort` calls (and / or external side effects) into named
    operations. The Conductor treats the body as opaque: it knows
    the name + params + the registry, and records whatever the body
    returns as evidence in the step payload.

    `params` is a JSON-shaped Mapping; tests can pass plain `dict`,
    runtime callers should pass an immutable `MappingProxyType` if
    they need to share params across steps without copy.
    """

    name: str
    params: Mapping[str, Any] = field(default_factory=dict[str, Any])


Step = SetpointStep | ActionStep
"""The closed discriminated union of step kinds the Conductor walks.

`check` is intentionally NOT a member of this union yet; it joins at
the next Stage-2 iteration once the post-condition shape (predicate
+ reading source + acceptance criterion) is locked. Mirrors the open
StepKind Literal in the Procedure aggregate which already lists
"check"; the Conductor enforces tighter typing pending design."""


@dataclass(frozen=True)
class ActionContext:
    """Dependencies + per-call inputs the Conductor passes to action bodies.

    Bundled so additive fields (correlation_id, procedure_id, a
    cancel-token, a structured logger) can land without churning
    every action body's signature. Bodies destructure what they need
    and ignore the rest.
    """

    control_port: ControlPort
    clock: Clock
    params: Mapping[str, Any]


ActionBody = Callable[[ActionContext], Awaitable[Mapping[str, Any]]]
"""Callable an `ActionRegistry` maps action names onto.

Returns a JSON-shaped `Mapping` recorded as `result_data` in the
step payload. Raising any `Control*Error` halts the Conductor and
records the failure; raising anything else propagates uncaught.
Bodies that want a domain-level "soft fail" return a result Mapping
carrying their own status field."""


class ActionRegistry(Protocol):
    """Read-only lookup from action name to `ActionBody`.

    A Protocol (not a concrete dict-backed class) so deployments can
    back the registry with whatever discovery mechanism fits: hand-
    built dict in tests, config-file loader in 2-BM, entry-point
    scan in a future plugin world. `InMemoryActionRegistry` (below)
    is the dict-backed default the Conductor's unit tests use.
    """

    def lookup(self, name: str) -> ActionBody | None: ...


@dataclass(frozen=True)
class InMemoryActionRegistry:
    """Dict-backed `ActionRegistry`; the default for tests + small deployments.

    Construct from a mapping at app wire-up time; the dict shape is
    intentional (not a callable Protocol) so missing-name lookups
    return None rather than raising, keeping the failure-recording
    path uniform with `Control*Error` paths.
    """

    bodies: Mapping[str, ActionBody]

    def lookup(self, name: str) -> ActionBody | None:
        return self.bodies.get(name)


@dataclass(frozen=True)
class ConductorFailure:
    """First step that raised a `Control*Error` or `UnknownActionError`.

    `error_class` is the simple class name (no module prefix); the
    `message` carries the formatted `str(exc)` output. Both land in
    the recorded step payload so log inspection from the read-side
    matches what's on the `ConductorResult`.
    """

    step_index: int
    step_kind: str
    target: str
    error_class: str
    message: str


@dataclass(frozen=True)
class ConductorResult:
    """Outcome of a `Conductor.execute` call.

    `completed_count` is the number of steps that fully ran AND
    recorded a success entry. The failing step (if any) is NOT
    counted in `completed_count`; its failure IS recorded in the
    logbook AND surfaced in `failure`.
    """

    procedure_id: UUID
    completed_count: int
    failure: ConductorFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


class Conductor:
    """Operation BC Layer-2 runtime: walks `Step`s via ControlPort + action registry.

    Stateless walker. Construct once at app wire-up time; call
    `execute` per Procedure execution. Per-call state lives on the
    returned `ConductorResult`.

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
        action_registry: ActionRegistry | None = None,
    ) -> None:
        self._control_port = control_port
        self._append_step = append_step
        self._clock = clock
        self._id_generator = id_generator
        self._action_registry: ActionRegistry = action_registry or InMemoryActionRegistry({})

    async def execute(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Walk `steps` in order; dispatch per kind + record outcome.

        Halts on the first `Control*Error` or `UnknownActionError`.
        The failing step is recorded in the logbook (`result="failed"`)
        BEFORE this returns; subsequent steps are NOT attempted. The
        Procedure's FSM is unchanged.

        Non-port, non-UnknownAction exceptions (programmer errors,
        KeyboardInterrupt, CancelledError) are NOT caught: they
        propagate to the caller so signals + cancellation behave
        normally and bugs surface.
        """
        envelope = _Envelope(
            procedure_id=procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        completed = 0
        for index, step in enumerate(steps):
            failure = await self._dispatch(step, index=index, envelope=envelope)
            if failure is not None:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=completed,
                    failure=failure,
                )
            completed += 1
        return ConductorResult(procedure_id=procedure_id, completed_count=completed)

    async def _dispatch(
        self,
        step: Step,
        *,
        index: int,
        envelope: "_Envelope",
    ) -> ConductorFailure | None:
        """Run one step + record outcome; return ConductorFailure on halt-condition."""
        if isinstance(step, SetpointStep):
            return await self._run_setpoint(step, index=index, envelope=envelope)
        return await self._run_action(step, index=index, envelope=envelope)

    async def _run_setpoint(
        self,
        step: SetpointStep,
        *,
        index: int,
        envelope: "_Envelope",
    ) -> ConductorFailure | None:
        payload_body: dict[str, Any] = {"address": step.address, "value": step.value}
        try:
            await self._control_port.write(step.address, step.value, wait=True)
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
                step_kind=_STEP_KIND_SETPOINT,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                step_kind=_STEP_KIND_SETPOINT,
                target=step.address,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        await self._record(
            envelope=envelope,
            step_kind=_STEP_KIND_SETPOINT,
            body=payload_body,
            result=_RESULT_OK,
        )
        return None

    async def _run_action(
        self,
        step: ActionStep,
        *,
        index: int,
        envelope: "_Envelope",
    ) -> ConductorFailure | None:
        payload_body: dict[str, Any] = {"name": step.name, "params": dict(step.params)}
        body = self._action_registry.lookup(step.name)
        if body is None:
            exc = UnknownActionError(step.name)
            await self._record(
                envelope=envelope,
                step_kind=_STEP_KIND_ACTION,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                step_kind=_STEP_KIND_ACTION,
                target=step.name,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        try:
            result_data = await body(
                ActionContext(
                    control_port=self._control_port,
                    clock=self._clock,
                    params=step.params,
                )
            )
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
                step_kind=_STEP_KIND_ACTION,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                step_kind=_STEP_KIND_ACTION,
                target=step.name,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        await self._record(
            envelope=envelope,
            step_kind=_STEP_KIND_ACTION,
            body={**payload_body, "result_data": dict(result_data)},
            result=_RESULT_OK,
        )
        return None

    async def _record(
        self,
        *,
        envelope: "_Envelope",
        step_kind: str,
        body: dict[str, Any],
        result: str,
        error_class: str | None = None,
        message: str | None = None,
    ) -> None:
        """Append a single step entry via the injected handler.

        The payload merges the kind-specific `body` with the
        Conductor-local `result` discriminator (plus `error_class` +
        `message` on failure). Future Stage-2 iterations may extend
        the body shape (pre/post readings, retry counts, etc.)
        additively.
        """
        payload: dict[str, Any] = {**body, "result": result}
        if error_class is not None:
            payload["error_class"] = error_class
        if message is not None:
            payload["message"] = message
        sampled_at = self._clock.now()
        entry = ProcedureStepInput(
            event_id=self._id_generator.new_id(),
            step_kind=step_kind,
            payload=payload,
            sampled_at=sampled_at,
            occurred_at=sampled_at,
        )
        await self._append_step(
            AppendProcedureSteps(procedure_id=envelope.procedure_id, entries=(entry,)),
            principal_id=envelope.principal_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            surface_id=envelope.surface_id,
        )


@dataclass(frozen=True)
class _Envelope:
    """Bag of per-execute envelope fields the Conductor threads to `_record`.

    Internal helper; avoids passing six args to every helper method.
    Frozen so accidental mutation mid-execute is a type error.
    """

    procedure_id: UUID
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


__all__ = [
    "ActionBody",
    "ActionContext",
    "ActionRegistry",
    "ActionStep",
    "Conductor",
    "ConductorFailure",
    "ConductorResult",
    "InMemoryActionRegistry",
    "SetpointStep",
    "Step",
]
