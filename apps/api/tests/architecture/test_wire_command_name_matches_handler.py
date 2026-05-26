"""Wire `command_name` must equal the slice handler's `_COMMAND_NAME`.

`_COMMAND_NAME` (defined as a module-level constant in
`cora/<bc>/features/<slice>/handler.py`) is the authoritative stable
label for a slice's command. It is written into event payloads /
projection rows and consumed by observability dashboards. The
wire-level `command_name="..."` argument (passed to `with_tracing`
and `with_idempotency` in `cora/<bc>/wire.py`) MUST match it, so
OTel span names and idempotency cache keys agree with the persisted
row label.

This catches the silent-drift failure mode where someone renames the
handler constant (or the wire literal) but not the other. Neither
the type-checker nor the test suite would otherwise catch it: the
two ends are decoupled string literals.

Scope: only slices that declare `_COMMAND_NAME` are checked. Queries
(`get_*` / `list_*`) and factory-built update handlers (for example
`make_clearance_update_handler`) do not declare the constant and are
out of scope here; their wire labels are checked by
`test_wire_completeness` for presence.
"""

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files


def _handler_command_name(handler_py: Path) -> str | None:
    """Return the `_COMMAND_NAME = "..."` literal from a handler module."""
    tree = ast.parse(handler_py.read_text())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if (
                isinstance(tgt, ast.Name)
                and tgt.id == "_COMMAND_NAME"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                return node.value.value
    return None


def _bind_slice_names(node: ast.AST) -> list[str]:
    """Return slice names of every `<name>.bind(...)` Call descendant.

    The walker matches `<name>.bind(...)` shape only; nested attribute
    chains like `pkg.mod.bind(...)` are skipped (the wire factory always
    calls `<slice>.bind(...)` where `<slice>` is imported as a module
    alias, so the value is always a bare `Name`).
    """
    out: list[str] = []
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "bind"
            and isinstance(n.func.value, ast.Name)
        ):
            out.append(n.func.value.id)
    return out


def _wire_command_name_for_slice(wire_src: str, slice_name: str) -> str | None:
    """Find every `command_name="..."` paired with `<slice_name>.bind(deps)`.

    Walks every Call expression in the wire function body. A Call is
    considered "scoped to this slice" iff it contains at least one
    `<slice_name>.bind(...)` AND no other `<other_slice>.bind(...)`.
    That restriction filters out the outer `<BC>Handlers(...)` Call
    (which contains every slice's bind + every slice's command_name)
    while still admitting both layers of the `with_tracing(
    with_idempotency(<slice>.bind(...), command_name=...),
    command_name=...)` sandwich.

    Both layers MUST carry the same `command_name=` literal; if they
    disagree the walker returns None and the test asserts on the
    mismatch via the "could not locate" branch. The whole-body walk
    (not just Handlers(...) keywords) admits conditional wirings
    built into a local variable, for example `re_debrief_run_handler` on
    the LLM-optional path.
    """
    tree = ast.parse(wire_src)
    matches: list[str] = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        binds = _bind_slice_names(call)
        if slice_name not in binds:
            continue
        if any(b != slice_name for b in binds):
            continue
        for inner in ast.walk(call):
            if (
                isinstance(inner, ast.keyword)
                and inner.arg == "command_name"
                and isinstance(inner.value, ast.Constant)
                and isinstance(inner.value.value, str)
            ):
                matches.append(inner.value.value)
    if not matches:
        return None
    unique = set(matches)
    return matches[0] if len(unique) == 1 else None


def _slices_with_command_name_constant() -> list[tuple[str, str, str]]:
    """Return (bc, slice_name, handler_command_name) for every slice
    whose handler.py declares `_COMMAND_NAME`."""
    out: list[tuple[str, str, str]] = []
    tracked = tracked_python_files()
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        for handler_py in sorted(
            f
            for f in tracked
            if f.name == "handler.py"
            and f.parent.parent == features
            and not f.parent.name.startswith("_")
        ):
            cmd = _handler_command_name(handler_py)
            if cmd is not None:
                out.append((bc, handler_py.parent.name, cmd))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("bc", "slice_name", "handler_command_name"),
    _slices_with_command_name_constant(),
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_wire_command_name_matches_handler_constant(
    bc: str, slice_name: str, handler_command_name: str
) -> None:
    wire_module = importlib.import_module(f"cora.{bc}.wire")
    wire_fn = getattr(wire_module, f"wire_{bc}", None)
    assert wire_fn is not None, f"cora.{bc}.wire.wire_{bc} not found"

    wire_src = inspect.getsource(wire_fn)
    wire_cmd = _wire_command_name_for_slice(wire_src, slice_name)

    assert wire_cmd is not None, (
        f"wire_{bc}: could not locate `command_name=...` paired with "
        f"`{slice_name}.bind(deps)`. The slice's handler declares "
        f"`_COMMAND_NAME = {handler_command_name!r}`; the wire factory "
        f"must pass the same literal to `with_tracing` / `with_idempotency`."
    )
    assert wire_cmd == handler_command_name, (
        f"wire_{bc}: `command_name={wire_cmd!r}` paired with "
        f"`{slice_name}.bind(...)` disagrees with "
        f"handler `_COMMAND_NAME = {handler_command_name!r}`. "
        f"The handler's constant is the source of truth (it labels "
        f"persisted rows + observability spans); update the wire literal "
        f"to match, or update both together if the row label is changing."
    )
