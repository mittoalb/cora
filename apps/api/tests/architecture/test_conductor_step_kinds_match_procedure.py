"""The Conductor's `Step` union must stay in sync with the Procedure aggregate's `StepKind`.

Pins two parallel declarations against drift:

  - `cora.operation.aggregates.procedure.state.STEP_KIND_VALUES` (the
    frozenset the `append_procedure_steps` handler validates entries
    against)
  - the per-kind `_STEP_KIND_*` constants in `cora.operation.conductor`
    (the strings the Conductor stamps into each recorded step's
    payload)

If someone adds a new `WaitStep` to the Conductor's `Step` union
without extending `STEP_KIND_VALUES` (or vice-versa), runtime
calls to `append_procedure_steps` start failing validation with
no CI signal. This test catches the divergence at fitness time.
"""

import pytest

from cora.operation import conductor as _conductor_module
from cora.operation.aggregates.procedure import STEP_KIND_VALUES


@pytest.mark.architecture
def test_conductor_step_kind_constants_match_procedure_step_kind_values() -> None:
    """Per-kind `_STEP_KIND_<X>` constants in conductor.py equal `STEP_KIND_VALUES`.

    The lifecycle pseudo-kind is intentionally excluded (it never
    lands on a recorded ProcedureStep; it only appears on
    ConductorFailure when conduct() catches a lifecycle handler
    exception).
    """
    conductor_kinds = frozenset(
        getattr(_conductor_module, name)
        for name in dir(_conductor_module)
        if name.startswith("_STEP_KIND_") and name != "_STEP_KIND_LIFECYCLE"
    )
    assert conductor_kinds == STEP_KIND_VALUES, (
        f"Conductor _STEP_KIND_* constants {sorted(conductor_kinds)} drift from "
        f"Procedure STEP_KIND_VALUES {sorted(STEP_KIND_VALUES)}. Add or remove "
        f"the missing constant to keep the Conductor's recorded step_kinds "
        f"in sync with what append_procedure_steps accepts."
    )


@pytest.mark.architecture
def test_conductor_step_union_arms_match_procedure_step_kind_values() -> None:
    """The `Step = SetpointStep | ActionStep | CheckStep` union has one arm per kind.

    Reads the `Step` type alias via `typing.get_args` and asserts the
    arm count equals `len(STEP_KIND_VALUES)`. New step types added
    to the union without a matching `STEP_KIND_VALUES` entry land
    here.
    """
    from typing import get_args

    union_arms = get_args(_conductor_module.Step)
    assert len(union_arms) == len(STEP_KIND_VALUES), (
        f"Conductor.Step union has {len(union_arms)} arms but "
        f"STEP_KIND_VALUES has {len(STEP_KIND_VALUES)} kinds. The two "
        f"declarations must stay one-to-one or recorded steps will fail "
        f"validation at append time."
    )
