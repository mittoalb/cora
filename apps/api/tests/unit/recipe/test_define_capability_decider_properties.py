"""Property-based tests for `define_capability.decide` (Recipe BC).

Mirrors the Access / Trust decider-PBT pattern on a Recipe BC
create-style command. Universal claims across generated inputs:

  - state=None + valid command + non-empty executor_shapes emits a
    single CapabilityDefined with the injected new_id / now.
  - state=Capability always raises CapabilityAlreadyExistsError,
    regardless of command.
  - Empty executor_shapes always raises InvalidExecutorShapesError.
  - Pure: same (state, command, now, new_id) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_CODE_NAMESPACE_PREFIX,
    CAPABILITY_NAME_MAX_LENGTH,
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityCode,
    CapabilityDefined,
    CapabilityName,
    ExecutorShape,
    InvalidExecutorShapesError,
)
from cora.recipe.features import define_capability
from cora.recipe.features.define_capability import DefineCapability
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_CODE_SUFFIX_MAX = CAPABILITY_CODE_MAX_LENGTH - len(CAPABILITY_CODE_NAMESPACE_PREFIX)
_CODE_SUFFIX = printable_ascii_text(min_size=1, max_size=_CODE_SUFFIX_MAX)
_NAME = printable_ascii_text(min_size=1, max_size=CAPABILITY_NAME_MAX_LENGTH)
_AFFORDANCES = st.frozensets(st.sampled_from(list(Affordance)), max_size=4)
_EXECUTOR_SHAPES = st.frozensets(st.sampled_from(list(ExecutorShape)), min_size=1)


def _command(
    *,
    code_suffix: str,
    name: str,
    shapes: frozenset[ExecutorShape],
    affordances: frozenset[Affordance],
) -> DefineCapability:
    return DefineCapability(
        code=f"{CAPABILITY_CODE_NAMESPACE_PREFIX}{code_suffix}",
        name=name,
        required_affordances=affordances,
        executor_shapes=shapes,
    )


def _capability(capability_id: UUID) -> Capability:
    return Capability(
        id=capability_id,
        code=CapabilityCode(f"{CAPABILITY_CODE_NAMESPACE_PREFIX}x"),
        name=CapabilityName("X"),
    )


@pytest.mark.unit
@given(
    code_suffix=_CODE_SUFFIX,
    name=_NAME,
    shapes=_EXECUTOR_SHAPES,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_capability_emits_exactly_one_event_with_injected_fields(
    code_suffix: str,
    name: str,
    shapes: frozenset[ExecutorShape],
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + valid command -> single CapabilityDefined with injected ids/time."""
    command = _command(code_suffix=code_suffix, name=name, shapes=shapes, affordances=affordances)
    events = define_capability.decide(state=None, command=command, now=now, new_id=new_id)
    assert events == [
        CapabilityDefined(
            capability_id=new_id,
            code=command.code,
            name=name,
            description=None,
            required_affordances=affordances,
            executor_shapes=shapes,
            parameters_schema=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    code_suffix=_CODE_SUFFIX,
    name=_NAME,
    shapes=_EXECUTOR_SHAPES,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_capability_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    code_suffix: str,
    name: str,
    shapes: frozenset[ExecutorShape],
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state -> CapabilityAlreadyExistsError, regardless of command."""
    command = _command(code_suffix=code_suffix, name=name, shapes=shapes, affordances=affordances)
    with pytest.raises(CapabilityAlreadyExistsError) as exc:
        define_capability.decide(
            state=_capability(existing_id), command=command, now=now, new_id=new_id
        )
    assert exc.value.capability_id == existing_id


@pytest.mark.unit
@given(
    code_suffix=_CODE_SUFFIX,
    name=_NAME,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_capability_with_empty_executor_shapes_always_raises(
    code_suffix: str,
    name: str,
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty executor_shapes -> InvalidExecutorShapesError, regardless of other fields."""
    command = _command(
        code_suffix=code_suffix,
        name=name,
        shapes=frozenset[ExecutorShape](),
        affordances=affordances,
    )
    with pytest.raises(InvalidExecutorShapesError):
        define_capability.decide(state=None, command=command, now=now, new_id=new_id)


@pytest.mark.unit
@given(
    code_suffix=_CODE_SUFFIX,
    name=_NAME,
    shapes=_EXECUTOR_SHAPES,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_capability_is_pure_same_input_same_output(
    code_suffix: str,
    name: str,
    shapes: frozenset[ExecutorShape],
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = _command(code_suffix=code_suffix, name=name, shapes=shapes, affordances=affordances)
    first = define_capability.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_capability.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
