"""Domain dataclasses (state / events / commands) must be frozen.

Aggregate state, events, and commands are values, not entities — they
participate in replay determinism and event-store immutability, and
their semantics depend on `==` and `hash` working from field tuples.
A mutable dataclass in any of these files breaks both: evolvers can
silently mutate prior state without emitting an event, and a frozenset
of commands or events can degenerate to a single representative.

This test AST-walks every `state.py`, `events.py`, and `command.py`
under `cora/<bc>/aggregates/...` or `cora/<bc>/features/...` and
fails if any `@dataclass(...)` decorator omits `frozen=True`.

Exceptions (Exception subclasses) and StrEnums are not dataclasses
and stay legitimate; only `@dataclass` usages are checked.

Part of the testing-techniques rollout. Complements:
  - test_decider_purity.py (no I/O / clock / random in deciders)
  - test_slice_contract.py (every slice has command + decider + handler + route + tool)
  - assert_never in evolve() (pyright enforces exhaustiveness statically).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


def _is_domain_file(f: Path) -> bool:
    """state.py or events.py inside an aggregate, or command.py inside a feature slice."""
    if f.name in {"state.py", "events.py"} and "aggregates" in f.parts:
        return True
    return f.name == "command.py" and "features" in f.parts


def _domain_files() -> list[Path]:
    tracked = tracked_python_files()
    bc_roots = [CORA_ROOT / bc for bc in BCS]
    return sorted(
        f
        for f in tracked
        if any(f.is_relative_to(root) for root in bc_roots) and _is_domain_file(f)
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _dataclass_violations(tree: ast.AST) -> list[str]:
    """Return one error message per non-frozen @dataclass decorator."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            # Match `@dataclass(...)` (call form) and bare `@dataclass`.
            # Bare form (no kwargs at all) is always non-frozen → violation.
            if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                violations.append(
                    f"line {decorator.lineno}: {node.name} uses bare @dataclass "
                    "(implicitly frozen=False); use @dataclass(frozen=True)"
                )
                continue
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            decorator_name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if decorator_name != "dataclass":
                continue
            frozen_kw = next((kw for kw in decorator.keywords if kw.arg == "frozen"), None)
            if frozen_kw is None:
                violations.append(f"line {decorator.lineno}: {node.name} omits frozen=True")
                continue
            if not (isinstance(frozen_kw.value, ast.Constant) and frozen_kw.value.value is True):
                rendered = ast.unparse(frozen_kw.value)
                violations.append(
                    f"line {decorator.lineno}: {node.name} has frozen={rendered} "
                    "(must be the literal True)"
                )
    return violations


@pytest.mark.architecture
@pytest.mark.parametrize("path", _domain_files(), ids=_qualified)
def test_domain_dataclasses_are_frozen(path: Path) -> None:
    """Every `@dataclass` in state/events/command files declares frozen=True."""
    tree = ast.parse(path.read_text())
    violations = _dataclass_violations(tree)
    assert not violations, (
        f"{_qualified(path)} contains non-frozen dataclass(es):\n  "
        + "\n  ".join(violations)
        + "\nDomain values (state / events / commands) must be immutable."
    )
