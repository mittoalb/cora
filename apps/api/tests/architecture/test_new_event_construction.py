"""`NewEvent(...)` may only be constructed inside `event_envelope.py`.

Phase 9b retrospective enforcement. The 9b arc made `principal_id`
required at the helper layer (`to_new_event(principal_id: UUID)`),
but the underlying `NewEvent` dataclass keeps `principal_id: UUID
| None` so test fixtures can simulate the historical pre-hook
NULL case. That looser type is safe IF every src code path goes
through `to_new_event`, which type-rejects None.

The gap the arch test closes: a future src file (handler, saga
adapter, projection writer) could bypass `to_new_event` and
construct `NewEvent(...)` directly. Such code would land outside
the helper's type-check guard, and a literal `principal_id=None`
or a typed-Optional intermediate would silently produce events
with NULL principal_id, defeating the day-1 ReBAC hook.

This test enforces the discipline structurally: scan every src
file under `cora/`, AST-detect any Call to `NewEvent`, allow only
the one site inside `event_envelope.py`. Test fixtures can do
whatever they want; production code goes through the helper.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT

# The single allowed construction site: `to_new_event` in the cross-BC
# envelope helper. Adding a second authorized constructor (for example,
# a future saga adapter that needs to build NewEvent objects with extra
# metadata) would require explicit allowlist update + reviewer sign-off.
_ALLOWED_FILE = CORA_ROOT / "infrastructure" / "event_envelope.py"


def _src_files() -> list[Path]:
    """Every `.py` file under `cora/` excluding the allowed file."""
    out: list[Path] = []
    for path in CORA_ROOT.rglob("*.py"):
        if path == _ALLOWED_FILE:
            continue
        out.append(path)
    return sorted(out)


def _new_event_call_lines(tree: ast.AST) -> list[int]:
    """Find every Call node whose func resolves to a name `NewEvent`."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "NewEvent") or (
            isinstance(func, ast.Attribute) and func.attr == "NewEvent"
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.unit
def test_new_event_only_constructed_in_envelope_helper() -> None:
    """Single arch test, not parametrized: scan all src files, fail
    loud if any constructs NewEvent outside `event_envelope.py`."""
    offenders: list[tuple[Path, list[int]]] = []
    for path in _src_files():
        source = path.read_text()
        if "NewEvent(" not in source:
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        sites = _new_event_call_lines(tree)
        if sites:
            offenders.append((path, sites))

    assert not offenders, (
        "Direct `NewEvent(...)` construction is only permitted in "
        "`cora/infrastructure/event_envelope.py` (the `to_new_event` "
        "helper). All other src code must go through that helper so "
        "the `principal_id: UUID` type-check enforces the day-1 ReBAC "
        "hook end-to-end. Offending sites:\n"
        + "\n".join(
            f"  - {p.relative_to(CORA_ROOT)} at line(s) {sorted(set(lines))}"
            for p, lines in offenders
        )
        + "\n\nIf you have a legitimate need (saga adapter, etc.), "
        "extend the allowlist in `tests/architecture/test_new_event_construction.py` "
        "with reviewer sign-off."
    )
