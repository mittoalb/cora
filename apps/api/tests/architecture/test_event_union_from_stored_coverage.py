"""Every event class in ``<Aggregate>Event`` union has a ``from_stored`` case.

The ``test_from_stored_wraps_payload`` fitness pins that each existing
``case "X":`` branch wraps ``KeyError`` / ``TypeError`` / ``AttributeError``
as ``ValueError``. It does NOT check that every event in the
``<Aggregate>Event`` discriminated union actually has a case at all.

A new event class that's added to the union but forgotten in the
``from_stored`` match statement silently falls through to the wildcard
arm and either raises a generic "unknown event_type" error at replay
time or, worse, gets dropped from a list comprehension that swallows
the exception. This fitness function catches the gap at commit time.

For every ``events.py``:
  1. Find the ``<Aggregate>Event = A | B | C`` type alias (or nested
     ``Union[...]`` shape).
  2. Find the ``from_stored`` function.
  3. For each ``case "X":`` arm, detect which class its body constructs.
  4. Pin: every class in the union has at least one case constructing it,
     AND every case constructs a class that's IN the union.

The legacy-rename dispatch pattern (a ``case "OldName":`` arm that
constructs the new dataclass) is intentional and stays accepted: as
long as the constructed class is in the union, extra case strings
aliased to it are fine.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


def _event_files() -> list[Path]:
    return sorted(
        f
        for f in tracked_python_files()
        if f.name == "events.py"
        and f.parent.parent.name == "aggregates"
        and f.parent.parent.parent.parent == CORA_ROOT
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _collect_names_in_union(node: ast.expr) -> list[str]:
    """Walk ``A | B | C`` (nested ``BinOp(BitOr)``) and return ``[A, B, C]``."""
    out: list[str] = []
    if isinstance(node, ast.Name):
        out.append(node.id)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        out.extend(_collect_names_in_union(node.left))
        out.extend(_collect_names_in_union(node.right))
    elif (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Union"
    ):
        # ``Union[A, B, C]`` shape (rare in CORA).
        slice_node = node.slice
        elements = slice_node.elts if isinstance(slice_node, ast.Tuple) else [slice_node]
        for elt in elements:
            out.extend(_collect_names_in_union(elt))
    return out


def _find_event_union(tree: ast.Module) -> tuple[str, list[str]] | None:
    """Find a top-level ``<X>Event = A | B | ...`` assignment.

    Skips ``AnnAssign`` (rare in this codebase for unions) and PEP 695
    ``type`` aliases (not used here yet).
    """
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.endswith("Event"):
            continue
        names = _collect_names_in_union(node.value)
        if len(names) >= 2:
            return target.id, names
    return None


def _find_from_stored(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "from_stored":
            return node
    return None


def _builder_target_class(call: ast.Call, case_scope: ast.AST) -> str | None:
    """Resolve the event class constructed by a ``deserialize_or_raise`` call.

    Recognises two shapes used by the ``cora.infrastructure.event_payload``
    helper:

      - ``deserialize_or_raise("X", lambda: ClassName(...))`` -> ``ClassName``
      - ``deserialize_or_raise("X", _build_x)`` -> walks the nested
        ``def _build_x()`` inside ``case_scope`` and returns the
        ``return ClassName(...)`` target.
    """
    if not (isinstance(call.func, ast.Name) and call.func.id == "deserialize_or_raise"):
        return None
    if len(call.args) < 2:
        return None
    builder = call.args[1]
    if isinstance(builder, ast.Lambda) and isinstance(builder.body, ast.Call):
        body_call = builder.body
        if isinstance(body_call.func, ast.Name):
            return body_call.func.id
        return None
    if isinstance(builder, ast.Name):
        for node in ast.walk(case_scope):
            if isinstance(node, ast.FunctionDef) and node.name == builder.id:
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.Return)
                        and isinstance(sub.value, ast.Call)
                        and isinstance(sub.value.func, ast.Name)
                    ):
                        return sub.value.func.id
        return None
    return None


def _collect_case_targets(func: ast.FunctionDef) -> dict[str, str | None]:
    """For each ``case "X":`` arm, return ``{X: ClassName}`` it constructs.

    Maps a case string to the name of the dataclass returned by its body.
    Recognises both the legacy ``return ClassName(...)`` shape and the
    ``return deserialize_or_raise("X", lambda: ClassName(...))`` /
    ``return deserialize_or_raise("X", _build_x)`` shapes introduced by
    ``cora.infrastructure.event_payload.deserialize_or_raise``.
    """
    out: dict[str, str | None] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Match):
            continue
        for case in node.cases:
            pattern = case.pattern
            if not (
                isinstance(pattern, ast.MatchValue)
                and isinstance(pattern.value, ast.Constant)
                and isinstance(pattern.value.value, str)
            ):
                continue
            case_str = pattern.value.value
            target: str | None = None
            for body_node in ast.walk(case):
                if not (
                    isinstance(body_node, ast.Return) and isinstance(body_node.value, ast.Call)
                ):
                    continue
                call = body_node.value
                if isinstance(call.func, ast.Name) and call.func.id == "deserialize_or_raise":
                    target = _builder_target_class(call, case)
                    break
                if isinstance(call.func, ast.Name):
                    target = call.func.id
                    break
            out[case_str] = target
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("events_file", _event_files(), ids=_qualified)
def test_every_event_in_union_has_from_stored_case(events_file: Path) -> None:
    qualified_module = _qualified(events_file)
    tree = ast.parse(events_file.read_text())

    union = _find_event_union(tree)
    if union is None:
        pytest.skip(f"{qualified_module}: no <X>Event union (likely single-event)")
    union_name, union_members = union
    union_set = set(union_members)

    from_stored = _find_from_stored(tree)
    assert from_stored is not None, (
        f"{qualified_module}: defines {union_name} but no from_stored function"
    )

    case_targets = _collect_case_targets(from_stored)
    constructed = {target for target in case_targets.values() if target is not None}

    missing = union_set - constructed
    assert not missing, (
        f"{qualified_module}.from_stored is missing cases that construct "
        f"{sorted(missing)} (members of {union_name}). New events added "
        "to the union must also be dispatched."
    )

    foreign = {
        case_str: target
        for case_str, target in case_targets.items()
        if target is not None and target not in union_set
    }
    assert not foreign, (
        f"{qualified_module}.from_stored has cases that construct classes "
        f"outside {union_name}: {foreign}. Either add the class to the "
        "union or fix the dispatch."
    )
