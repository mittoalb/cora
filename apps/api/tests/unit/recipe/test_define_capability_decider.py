"""Unit tests for the `define_capability` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityCode,
    CapabilityName,
    ExecutorShape,
    InvalidCapabilityCodeError,
    InvalidCapabilityNameError,
    InvalidCapabilityParametersSchemaError,
    InvalidExecutorShapesError,
    RecipeCapabilityDefined,
)
from cora.recipe.features.define_capability import DefineCapability, decide

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)


def _cmd(**overrides: object) -> DefineCapability:
    base: dict[str, object] = dict(
        code="cora.capability.flyscan",
        name="FlyScan",
        required_affordances=frozenset({Affordance.ROTATABLE}),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )
    base.update(overrides)
    return DefineCapability(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_decide_emits_capability_defined_for_fresh_stream() -> None:
    new_id = uuid4()
    events = decide(state=None, command=_cmd(), now=_NOW, new_id=new_id)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RecipeCapabilityDefined)
    assert event.capability_id == new_id
    assert event.code == "cora.capability.flyscan"
    assert event.name == "FlyScan"


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_present() -> None:
    state = Capability(
        id=uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
    )
    with pytest.raises(CapabilityAlreadyExistsError) as exc:
        decide(state=state, command=_cmd(), now=_NOW, new_id=uuid4())
    assert exc.value.capability_id == state.id


@pytest.mark.unit
def test_decide_raises_on_bad_code_namespace() -> None:
    with pytest.raises(InvalidCapabilityCodeError):
        decide(state=None, command=_cmd(code="flyscan"), now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_raises_on_whitespace_only_name() -> None:
    with pytest.raises(InvalidCapabilityNameError):
        decide(state=None, command=_cmd(name="   "), now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_raises_on_empty_executor_shapes() -> None:
    with pytest.raises(InvalidExecutorShapesError):
        decide(
            state=None,
            command=_cmd(executor_shapes=frozenset[ExecutorShape]()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_allows_empty_required_affordances() -> None:
    """Pattern P: empty is valid for required_affordances (parameter-driven Capabilities)."""
    events = decide(
        state=None,
        command=_cmd(required_affordances=frozenset[Affordance]()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    assert events[0].required_affordances == frozenset()


@pytest.mark.unit
def test_decide_raises_on_malformed_parameters_schema() -> None:
    """parameters_schema must be a valid in-subset JSON Schema."""
    with pytest.raises(InvalidCapabilityParametersSchemaError):
        decide(
            state=None,
            command=_cmd(parameters_schema={"$ref": "#/definitions/bad"}),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_is_pure() -> None:
    new_id = uuid4()
    e1 = decide(state=None, command=_cmd(), now=_NOW, new_id=new_id)
    e2 = decide(state=None, command=_cmd(), now=_NOW, new_id=new_id)
    assert e1 == e2
