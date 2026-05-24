"""Every ExecutorShape enum value is referenced via the enum, not as a bare string.

`ExecutorShape` is a closed v1 StrEnum at
`cora.recipe.aggregates.capability.executor_shape` whose values
(`"Method"`, `"Procedure"`) participate in cross-BC guards
(`MethodCapabilityExecutorMismatchError`,
`ProcedureCapabilityExecutorMismatchError`). The risk this fitness
guards against: a future change to the enum value (or a refactor)
silently leaves behind a bare-string check (`if shape_str ==
"Method":`) that no longer matches the enum.

For each declared ExecutorShape member, this test asserts at least
one reference of the canonical form `ExecutorShape.<NAME>` exists
in tracked source code OUTSIDE the enum's own module. If the only
references are the enum declaration itself, the value is effectively
orphaned and any bare-string usage downstream would drift silently.

Drift catcher only: bare-string checks at unrelated layers
(stream_type strings, Caution-target kind strings) are NOT the
audit's concern because they don't carry executor-shape semantics.
The positive-presence assertion is the cheapest sufficient guard.
"""

from __future__ import annotations

import pytest

from cora.recipe.aggregates.capability.executor_shape import ExecutorShape
from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_ENUM_FILE = CORA_ROOT / "recipe" / "aggregates" / "capability" / "executor_shape.py"


@pytest.mark.architecture
@pytest.mark.parametrize("member", list(ExecutorShape), ids=lambda m: m.name)
def test_executor_shape_member_is_referenced(member: ExecutorShape) -> None:
    needle = f"ExecutorShape.{member.name}"
    hits: list[str] = []
    for path in tracked_python_files():
        if path == _ENUM_FILE:
            continue
        if needle in path.read_text():
            hits.append(str(path.relative_to(CORA_ROOT)))
    assert hits, (
        f"ExecutorShape.{member.name} ({member.value!r}) is declared but "
        "no source file references it via the enum. Cross-BC guards "
        "may have drifted to bare-string comparisons; restore an "
        f"`ExecutorShape.{member.name}` reference at the call site."
    )
