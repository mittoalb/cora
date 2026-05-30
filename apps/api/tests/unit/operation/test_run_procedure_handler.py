"""Unit-tier tests for the `run_procedure` slice.

Covers:

  - handler dispatches to Conductor.conduct() with passed-through
    envelope (procedure_id + principal_id + correlation_id +
    causation_id + surface_id)
  - handler returns RunProcedureResult mirroring ConductorResult
    (procedure_id + completed_count + succeeded + failure)
  - handler raises UnauthorizedError when the Authorize port denies
  - wire-type converters: SetpointStep / ActionStep / CheckStep
    round-trip through Pydantic + step_from_wire
  - criterion converters: Equals / WithinTolerance round-trip
  - lists on the wire coerce to tuples in the in-process Step values
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import Allow, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.conductor import (
    ActionStep,
    CheckStep,
    ConductorFailure,
    ConductorResult,
    Equals,
    SetpointStep,
    Step,
    WithinTolerance,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.run_procedure.command import RunProcedure, RunProcedureResult
from cora.operation.features.run_procedure.handler import bind
from cora.operation.features.run_procedure.route import (
    RunProcedureRequest,
    criterion_from_wire,
    result_to_wire,
    step_from_wire,
)


@dataclass
class _FakeAuthz:
    """Stand-in for the Authorize port; configurable allow/deny."""

    deny_reason: str | None = None

    async def authorize(
        self,
        *,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID,
    ) -> Allow | Deny:
        _ = (principal_id, command_name, conduit_id, surface_id)
        return Deny(reason=self.deny_reason) if self.deny_reason is not None else Allow()


@dataclass
class _ConductCall:
    """One recorded invocation of the fake Conductor.conduct()."""

    procedure_id: UUID
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID
    steps: Sequence[Step]


@dataclass
class _FakeConductor:
    """Fake Conductor whose .conduct() captures the call + returns a canned result."""

    result: ConductorResult
    calls: list[_ConductCall] = field(default_factory=list[_ConductCall])

    async def conduct(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        self.calls.append(
            _ConductCall(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
                steps=steps,
            )
        )
        return self.result


def _deps(authz: _FakeAuthz) -> Kernel:
    """Minimal Kernel-shaped stub; only `.authz` is exercised."""

    @dataclass
    class _MinimalKernel:
        authz: _FakeAuthz

    return _MinimalKernel(authz=authz)  # type: ignore[return-value]


# --- handler dispatch ---------------------------------------------------


@pytest.mark.unit
async def test_run_procedure_handler_dispatches_to_conductor_with_envelope() -> None:
    procedure_id = uuid4()
    principal_id = uuid4()
    correlation_id = uuid4()
    causation_id = uuid4()
    surface_id = uuid4()
    conductor = _FakeConductor(result=ConductorResult(procedure_id=procedure_id, completed_count=2))
    handler = bind(_deps(_FakeAuthz()), conductor=conductor)  # type: ignore[arg-type]
    steps: tuple[Step, ...] = (
        SetpointStep(address="2bma:rot:val", value=45.0),
        SetpointStep(address="2bma:cam:exposure", value=0.025),
    )
    result = await handler(
        RunProcedure(procedure_id=procedure_id, steps=steps),
        principal_id=principal_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        surface_id=surface_id,
    )
    assert len(conductor.calls) == 1
    call = conductor.calls[0]
    assert call.procedure_id == procedure_id
    assert call.principal_id == principal_id
    assert call.correlation_id == correlation_id
    assert call.causation_id == causation_id
    assert call.surface_id == surface_id
    assert call.steps == steps
    assert isinstance(result, RunProcedureResult)
    assert result.procedure_id == procedure_id
    assert result.completed_count == 2
    assert result.succeeded is True
    assert result.failure is None


@pytest.mark.unit
async def test_run_procedure_handler_propagates_failure_from_conductor() -> None:
    procedure_id = uuid4()
    failure = ConductorFailure(
        step_index=0,
        step_kind="setpoint",
        target="2bma:rot:val",
        error_class="ControlNotConnectedError",
        message="Control address '2bma:rot:val' not connected",
    )
    conductor = _FakeConductor(
        result=ConductorResult(procedure_id=procedure_id, completed_count=0, failure=failure)
    )
    handler = bind(_deps(_FakeAuthz()), conductor=conductor)  # type: ignore[arg-type]
    result = await handler(
        RunProcedure(procedure_id=procedure_id, steps=()),
        principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert result.succeeded is False
    assert result.failure == failure


@pytest.mark.unit
async def test_run_procedure_handler_raises_unauthorized_when_authz_denies() -> None:
    conductor = _FakeConductor(result=ConductorResult(procedure_id=uuid4(), completed_count=0))
    handler = bind(_deps(_FakeAuthz(deny_reason="no permission")), conductor=conductor)  # type: ignore[arg-type]
    with pytest.raises(UnauthorizedError, match="no permission"):
        await handler(
            RunProcedure(procedure_id=uuid4(), steps=()),
            principal_id=uuid4(),
            correlation_id=uuid4(),
        )
    # Conductor is not invoked when authz denies.
    assert conductor.calls == []


# --- wire-type converters ----------------------------------------------


@pytest.mark.unit
def test_setpoint_step_round_trips_through_wire() -> None:
    body = RunProcedureRequest.model_validate(
        {
            "steps": [
                {"kind": "setpoint", "address": "2bma:rot:val", "value": 45.0},
                {
                    "kind": "setpoint",
                    "address": "2bma:cam:exposure",
                    "value": 0.025,
                    "verify": True,
                },
            ]
        }
    )
    steps = [step_from_wire(s) for s in body.steps]
    assert isinstance(steps[0], SetpointStep)
    assert steps[0].address == "2bma:rot:val"
    assert steps[0].value == 45.0
    assert steps[0].verify is False
    assert isinstance(steps[1], SetpointStep)
    assert steps[1].verify is True


@pytest.mark.unit
def test_action_step_round_trips_through_wire() -> None:
    body = RunProcedureRequest.model_validate(
        {"steps": [{"kind": "action", "name": "home_motor", "params": {"axis": "rot"}}]}
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, ActionStep)
    assert step.name == "home_motor"
    assert step.params == {"axis": "rot"}


@pytest.mark.unit
def test_check_step_with_equals_round_trips_through_wire() -> None:
    body = RunProcedureRequest.model_validate(
        {
            "steps": [
                {
                    "kind": "check",
                    "address": "2bma:rot:rbv",
                    "criterion": {"kind": "equals", "expected": 45.0},
                }
            ]
        }
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, CheckStep)
    assert step.address == "2bma:rot:rbv"
    assert isinstance(step.criterion, Equals)
    assert step.criterion.expected == 45.0


@pytest.mark.unit
def test_check_step_with_within_tolerance_round_trips_through_wire() -> None:
    body = RunProcedureRequest.model_validate(
        {
            "steps": [
                {
                    "kind": "check",
                    "address": "2bma:temp:rbv",
                    "criterion": {"kind": "within_tolerance", "expected": 295.0, "tolerance": 0.5},
                }
            ]
        }
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, CheckStep)
    assert isinstance(step.criterion, WithinTolerance)
    assert step.criterion.expected == 295.0
    assert step.criterion.tolerance == 0.5


@pytest.mark.unit
def test_setpoint_value_list_on_wire_coerces_to_tuple_in_process() -> None:
    body = RunProcedureRequest.model_validate(
        {"steps": [{"kind": "setpoint", "address": "2bma:waveform", "value": [1.0, 2.0, 3.0]}]}
    )
    step = step_from_wire(body.steps[0])
    assert isinstance(step, SetpointStep)
    assert step.value == (1.0, 2.0, 3.0)
    assert isinstance(step.value, tuple)


@pytest.mark.unit
def test_equals_expected_list_on_wire_coerces_to_tuple_in_process() -> None:
    wire = _criterion_wire_from_dict({"kind": "equals", "expected": [1, 2, 3]})
    criterion = criterion_from_wire(wire)
    assert isinstance(criterion, Equals)
    assert criterion.expected == (1, 2, 3)
    assert isinstance(criterion.expected, tuple)


def _criterion_wire_from_dict(d: dict[str, Any]) -> Any:
    """Parse a single criterion dict through the wire model union."""
    body = RunProcedureRequest.model_validate(
        {"steps": [{"kind": "check", "address": "x", "criterion": d}]}
    )
    return body.steps[0].criterion  # type: ignore[union-attr]


@pytest.mark.unit
def test_unknown_step_kind_is_rejected_by_pydantic_at_parse_time() -> None:
    """Discriminated union catches malformed step kinds before the handler runs."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RunProcedureRequest.model_validate(
            {"steps": [{"kind": "lifecycle", "address": "x", "value": 1.0}]}
        )


@pytest.mark.unit
def test_result_to_wire_serializes_success() -> None:
    procedure_id = uuid4()
    result = RunProcedureResult(
        procedure_id=procedure_id, completed_count=3, succeeded=True, failure=None
    )
    wire = result_to_wire(result)
    assert wire.procedure_id == procedure_id
    assert wire.completed_count == 3
    assert wire.succeeded is True
    assert wire.failure is None


@pytest.mark.unit
def test_result_to_wire_serializes_failure() -> None:
    procedure_id = uuid4()
    failure = ConductorFailure(
        step_index=1,
        step_kind="check",
        target="2bma:rot:rbv",
        error_class="CheckFailedError",
        message="value 12.5 did not equal expected 45.0",
    )
    result = RunProcedureResult(
        procedure_id=procedure_id, completed_count=1, succeeded=False, failure=failure
    )
    wire = result_to_wire(result)
    assert wire.succeeded is False
    assert wire.failure is not None
    assert wire.failure.step_index == 1
    assert wire.failure.step_kind == "check"
    assert wire.failure.target == "2bma:rot:rbv"
    assert wire.failure.error_class == "CheckFailedError"
    assert "did not equal" in wire.failure.message


# --- lifecycle-failure step_index=None survives the wire round-trip ----


@pytest.mark.unit
def test_result_to_wire_serializes_lifecycle_failure_with_null_step_index() -> None:
    """Lifecycle failures carry step_index=None; the wire model must accept it."""
    procedure_id = uuid4()
    failure = ConductorFailure(
        step_index=None,
        step_kind="lifecycle",
        target="start",
        error_class="RuntimeError",
        message="Procedure not in Defined",
    )
    result = RunProcedureResult(
        procedure_id=procedure_id, completed_count=0, succeeded=False, failure=failure
    )
    wire = result_to_wire(result)
    assert wire.failure is not None
    assert wire.failure.step_index is None
    assert wire.failure.step_kind == "lifecycle"
    assert wire.failure.target == "start"


@pytest.mark.unit
def test_run_procedure_request_with_empty_step_list_is_valid() -> None:
    body = RunProcedureRequest.model_validate({"steps": []})
    assert body.steps == []


@pytest.mark.unit
def test_run_procedure_request_default_is_empty_step_list() -> None:
    body = RunProcedureRequest.model_validate({})
    assert body.steps == []
