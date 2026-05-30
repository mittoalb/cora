"""Behavioural tests for the Operation BC `Conductor`.

Coverage spans both step kinds shipped to date (setpoint + action):

  Setpoint:
  - empty steps -> trivially succeeds, no handler call
  - 3 setpoints -> 3 ControlPort writes + 3 step entries recorded
  - first write raises ControlNotConnectedError -> halt at index 0,
    failure entry recorded, ConductorResult.failure populated
  - middle write raises ControlTimeoutError -> halt at index N,
    earlier successes recorded, failure entry for the failing step,
    remaining steps untouched
  - non-port exception (asyncio.CancelledError) propagates without
    being caught + without recording anything
  - recorded payload shape (address + value + result + error_class on
    failure) survives across kind values + tuple values

  Action:
  - registered name + body invoked -> result_data recorded in payload
  - unknown name -> UnknownActionError failure recorded + halt
  - body raises ControlTimeoutError -> failure recorded + halt
  - body receives ControlPort + Clock + params via ActionContext
  - mixed setpoint + action step list walked in order

The unit tier uses `InMemoryControlPort` plus a fake append-step
handler that captures each call's command + envelope into a list. No
real handler wiring, no Procedure event store, no step store; the
Conductor's contract is "call the handler with the right args" and
the fake asserts on that.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.conductor import (
    ActionContext,
    ActionStep,
    Conductor,
    ConductorFailure,
    ConductorResult,
    InMemoryActionRegistry,
    SetpointStep,
)
from cora.operation.features.append_procedure_step.command import AppendProcedureSteps
from cora.operation.ports.control_port import ControlTimeoutError, Reading

_FIXED_NOW = datetime(2026, 5, 30, 9, 0, 0, tzinfo=UTC)


@dataclass
class _AppendCall:
    """One recorded invocation of the fake append-step handler."""

    command: AppendProcedureSteps
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


@dataclass
class _FakeAppendStep:
    """Fake `Handler` for the append_procedure_step slice.

    Records every call; returns the entry count to match the real
    handler's `int` return type. Tests assert against `calls`.
    """

    calls: list[_AppendCall] = field(default_factory=list[_AppendCall])

    async def __call__(
        self,
        command: AppendProcedureSteps,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        self.calls.append(
            _AppendCall(
                command=command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        )
        return len(command.entries)


@dataclass
class _SequenceIdGenerator:
    """Deterministic id_generator that returns a pre-supplied list of ids.

    Lets tests pin event_id values into the recorded entries so the
    payload assertion is exact. Raises on exhaustion so missing ids
    are loud, not silent.
    """

    ids: list[UUID]
    _index: int = 0

    def new_id(self) -> UUID:
        if self._index >= len(self.ids):
            raise RuntimeError("FixedIdGenerator exhausted")
        out = self.ids[self._index]
        self._index += 1
        return out


def _conductor(
    port: InMemoryControlPort,
    appender: _FakeAppendStep,
    *,
    ids: Sequence[UUID] = (),
    registry: InMemoryActionRegistry | None = None,
) -> Conductor:
    return Conductor(
        control_port=port,
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator(list(ids)),
        action_registry=registry,
    )


# --- setpoint coverage --------------------------------------------------


@pytest.mark.unit
async def test_execute_with_empty_steps_succeeds_without_handler_call() -> None:
    """Zero steps -> ConductorResult(completed_count=0); no handler call."""
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(),
    )
    assert result.completed_count == 0
    assert result.succeeded is True
    assert result.failure is None
    assert appender.calls == []


@pytest.mark.unit
async def test_execute_setpoints_writes_each_step_via_control_port_in_order() -> None:
    """Three setpoints -> three sequential writes; final values visible via read."""
    port = InMemoryControlPort(now=lambda: _FIXED_NOW)
    port.simulate_connect("2bma:rot:val")
    port.simulate_connect("2bma:cam:exposure")
    port.simulate_connect("2bma:shutter:open")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4() for _ in range(3)])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=45.0),
            SetpointStep(address="2bma:cam:exposure", value=0.025),
            SetpointStep(address="2bma:shutter:open", value=True),
        ),
    )
    assert result.completed_count == 3
    assert result.succeeded is True
    assert (await port.read("2bma:rot:val")).value == 45.0
    assert (await port.read("2bma:cam:exposure")).value == 0.025
    assert (await port.read("2bma:shutter:open")).value is True


@pytest.mark.unit
async def test_execute_setpoint_records_success_entry_with_expected_payload() -> None:
    """Each successful write produces one append call with the expected payload."""
    port = InMemoryControlPort(now=lambda: _FIXED_NOW)
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    procedure_id = uuid4()
    principal_id = uuid4()
    correlation_id = uuid4()
    event_id = uuid4()
    conductor = _conductor(port, appender, ids=[event_id])
    await conductor.execute(
        procedure_id=procedure_id,
        principal_id=principal_id,
        correlation_id=correlation_id,
        steps=(SetpointStep(address="2bma:rot:val", value=12.5),),
    )
    assert len(appender.calls) == 1
    call = appender.calls[0]
    assert call.command.procedure_id == procedure_id
    assert call.principal_id == principal_id
    assert call.correlation_id == correlation_id
    assert len(call.command.entries) == 1
    entry = call.command.entries[0]
    assert entry.event_id == event_id
    assert entry.step_kind == "setpoint"
    assert entry.sampled_at == _FIXED_NOW
    assert entry.occurred_at == _FIXED_NOW
    assert entry.payload == {
        "address": "2bma:rot:val",
        "value": 12.5,
        "result": "ok",
    }


@pytest.mark.unit
async def test_execute_halts_at_first_not_connected_error_on_setpoint() -> None:
    """First write raises ControlNotConnectedError -> failure at index 0."""
    port = InMemoryControlPort()  # nothing connected
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    procedure_id = uuid4()
    result = await conductor.execute(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=1.0),
            SetpointStep(address="2bma:cam:exposure", value=0.01),
        ),
    )
    assert result.completed_count == 0
    assert result.succeeded is False
    assert result.failure == ConductorFailure(
        step_index=0,
        step_kind="setpoint",
        target="2bma:rot:val",
        error_class="ControlNotConnectedError",
        message="Control address '2bma:rot:val' not connected",
    )
    # Exactly one failure entry recorded; the second step is untouched.
    assert len(appender.calls) == 1
    failure_entry = appender.calls[0].command.entries[0]
    assert failure_entry.payload["result"] == "failed"
    assert failure_entry.payload["error_class"] == "ControlNotConnectedError"
    assert "not connected" in failure_entry.payload["message"]


@pytest.mark.unit
async def test_execute_records_earlier_setpoint_successes_before_middle_failure() -> None:
    """Middle step failure leaves earlier success records + a failure record."""
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    # 2bma:cam:exposure NEVER simulate_connect'd -> NotConnected on second write
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4() for _ in range(2)])
    procedure_id = uuid4()
    result = await conductor.execute(
        procedure_id=procedure_id,
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address="2bma:rot:val", value=1.0),
            SetpointStep(address="2bma:cam:exposure", value=0.01),
            SetpointStep(address="2bma:shutter:open", value=True),
        ),
    )
    assert result.completed_count == 1
    assert result.failure is not None
    assert result.failure.step_index == 1
    assert result.failure.target == "2bma:cam:exposure"
    # 2 append calls: one OK at index 0, one FAILED at index 1; index 2 never tried.
    assert len(appender.calls) == 2
    assert appender.calls[0].command.entries[0].payload["result"] == "ok"
    assert appender.calls[1].command.entries[0].payload["result"] == "failed"


@pytest.mark.unit
async def test_execute_passes_through_causation_and_surface_ids() -> None:
    """Optional envelope fields reach the handler verbatim."""
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    causation_id = uuid4()
    surface_id = uuid4()
    await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address="2bma:rot:val", value=1.0),),
        causation_id=causation_id,
        surface_id=surface_id,
    )
    assert appender.calls[0].causation_id == causation_id
    assert appender.calls[0].surface_id == surface_id


@pytest.mark.unit
async def test_execute_does_not_catch_non_port_exceptions_on_setpoint() -> None:
    """A CancelledError mid-write propagates; nothing is recorded for it."""

    class _CancellingPort:
        async def read(self, _address: str) -> Reading:  # pragma: no cover  # unused
            raise NotImplementedError

        async def write(self, *_args: Any, **_kwargs: Any) -> None:
            raise asyncio.CancelledError

        def subscribe(self, _address: str) -> AsyncIterator[Reading]:  # pragma: no cover  # unused
            raise NotImplementedError

    appender = _FakeAppendStep()
    conductor = Conductor(
        control_port=_CancellingPort(),  # type: ignore[arg-type]
        append_step=appender,
        clock=FakeClock(_FIXED_NOW),
        id_generator=_SequenceIdGenerator([]),
    )
    with pytest.raises(asyncio.CancelledError):
        await conductor.execute(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(SetpointStep(address="anywhere", value=1.0),),
        )
    assert appender.calls == []


@pytest.mark.unit
def test_conductor_result_succeeded_property_reflects_failure_absence() -> None:
    """`.succeeded` is True iff `.failure is None`."""
    ok = ConductorResult(procedure_id=uuid4(), completed_count=3, failure=None)
    bad = ConductorResult(
        procedure_id=uuid4(),
        completed_count=1,
        failure=ConductorFailure(
            step_index=1, step_kind="setpoint", target="x", error_class="y", message="z"
        ),
    )
    assert ok.succeeded is True
    assert bad.succeeded is False


# --- action coverage ----------------------------------------------------


@pytest.mark.unit
async def test_execute_action_invokes_registered_body_and_records_result_data() -> None:
    """Action name resolves to body; body's return Mapping lands in payload."""
    captured: list[ActionContext] = []

    async def home_motor(ctx: ActionContext) -> Mapping[str, Any]:
        captured.append(ctx)
        return {"final_position": 0.0, "homed": True}

    registry = InMemoryActionRegistry({"home_motor": home_motor})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    event_id = uuid4()
    conductor = _conductor(port, appender, ids=[event_id], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="home_motor", params={"axis": "rot"}),),
    )
    assert result.succeeded is True
    assert result.completed_count == 1
    assert len(captured) == 1
    assert captured[0].params == {"axis": "rot"}
    assert captured[0].control_port is port
    entry = appender.calls[0].command.entries[0]
    assert entry.step_kind == "action"
    assert entry.payload == {
        "name": "home_motor",
        "params": {"axis": "rot"},
        "result": "ok",
        "result_data": {"final_position": 0.0, "homed": True},
    }


@pytest.mark.unit
async def test_execute_action_unknown_name_records_failure_and_halts() -> None:
    """Unknown action name -> UnknownActionError, failure recorded, halt."""
    registry = InMemoryActionRegistry({})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            ActionStep(name="nope", params={}),
            ActionStep(name="also_nope", params={}),
        ),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.step_index == 0
    assert result.failure.step_kind == "action"
    assert result.failure.target == "nope"
    assert result.failure.error_class == "UnknownActionError"
    # Only one record (the failure); the second action is untouched.
    assert len(appender.calls) == 1
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "failed"
    assert payload["error_class"] == "UnknownActionError"
    assert payload["name"] == "nope"


@pytest.mark.unit
async def test_execute_action_body_raising_control_error_records_failure_and_halts() -> None:
    """Body raising a Control*Error halts the Conductor + records the failure."""

    async def picky(_ctx: ActionContext) -> Mapping[str, Any]:
        raise ControlTimeoutError("test_pv", 0.5)

    registry = InMemoryActionRegistry({"picky": picky})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="picky"),),
    )
    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "ControlTimeoutError"
    assert result.failure.step_kind == "action"
    assert result.failure.target == "picky"
    payload = appender.calls[0].command.entries[0].payload
    assert payload["result"] == "failed"
    assert payload["error_class"] == "ControlTimeoutError"


@pytest.mark.unit
async def test_execute_action_body_raising_non_port_exception_propagates() -> None:
    """Generic exceptions in a body propagate; the Conductor does not swallow them."""

    async def buggy(_ctx: ActionContext) -> Mapping[str, Any]:
        raise RuntimeError("oops")

    registry = InMemoryActionRegistry({"buggy": buggy})
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[], registry=registry)
    with pytest.raises(RuntimeError, match="oops"):
        await conductor.execute(
            procedure_id=uuid4(),
            principal_id=uuid4(),
            correlation_id=uuid4(),
            steps=(ActionStep(name="buggy"),),
        )
    assert appender.calls == []


@pytest.mark.unit
async def test_execute_walks_mixed_setpoint_and_action_steps_in_order() -> None:
    """Setpoint + action in the same step list run sequentially, in order."""
    invocations: list[str] = []

    async def open_shutter(_ctx: ActionContext) -> Mapping[str, Any]:
        invocations.append("open_shutter")
        return {"state": "open"}

    async def close_shutter(_ctx: ActionContext) -> Mapping[str, Any]:
        invocations.append("close_shutter")
        return {"state": "closed"}

    registry = InMemoryActionRegistry(
        {"open_shutter": open_shutter, "close_shutter": close_shutter}
    )
    port = InMemoryControlPort()
    port.simulate_connect("2bma:rot:val")
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4() for _ in range(3)], registry=registry)
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            ActionStep(name="open_shutter"),
            SetpointStep(address="2bma:rot:val", value=90.0),
            ActionStep(name="close_shutter"),
        ),
    )
    assert result.succeeded is True
    assert result.completed_count == 3
    assert invocations == ["open_shutter", "close_shutter"]
    # 3 recorded entries in order: action / setpoint / action.
    kinds = [c.command.entries[0].step_kind for c in appender.calls]
    assert kinds == ["action", "setpoint", "action"]


@pytest.mark.unit
async def test_execute_action_default_registry_is_empty_when_omitted() -> None:
    """Conductor with no registry treats every action name as unknown."""
    port = InMemoryControlPort()
    appender = _FakeAppendStep()
    conductor = _conductor(port, appender, ids=[uuid4()])
    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(ActionStep(name="any_name"),),
    )
    assert result.failure is not None
    assert result.failure.error_class == "UnknownActionError"
