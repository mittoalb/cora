"""Event payload collection fields use immutable types.

Per the 2026-05-22 audit (D15) and the project convention exemplified
by ``Plan.wires`` (``frozenset[Wire]``) and Run's
``tuple[CautionAcknowledgement, ...]``: event payloads must declare
collection-typed fields with immutable types so that a payload dict
shared by reference into folded state can't be mutated post-fold.

This fitness function rejects:

  - ``list[X]``  →  use ``tuple[X, ...]``
  - ``set[X]``   →  use ``frozenset[X]``

``dict[X, Y]`` is deliberately NOT pinned: JSON-schema-shaped payloads
are intrinsically freeform dicts; pinning ``Mapping[X, Y]`` would
document intent without enforcing runtime immutability. The companion
defence for dict aliasing (B1 from the audit) is shallow-copy on fold
in the evolver, addressed in Phase β.

``MUTABLE_COLLECTION_EVENT_FIELDS`` is the explicit work-tracker for
known list/set fields awaiting migration. Phase β migrates the types
and removes the matching allowlist entries.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


# Entries are <qualified-event-class>.<field-name>. Each removed when
# Phase β migrates the type to tuple[...] / frozenset[...].
MUTABLE_COLLECTION_EVENT_FIELDS: frozenset[str] = frozenset(
    {
        # D15 (audit-explicit): list[UUID] / list[str] in MethodDefined.
        "cora.recipe.aggregates.method.events.MethodDefined.needed_families",
        "cora.recipe.aggregates.method.events.MethodDefined.needed_supplies",
        # Found by this fitness function (audit-implicit; same rule).
        "cora.operation.aggregates.procedure.events.ProcedureRegistered.target_asset_ids",
        "cora.recipe.aggregates.plan.events.PlanDefined.asset_ids",
        "cora.recipe.aggregates.plan.events.PlanDefined.method_needed_families_snapshot",
        "cora.trust.aggregates.policy.events.PolicyDefined.permitted_principals",
        "cora.trust.aggregates.policy.events.PolicyDefined.permitted_commands",
    }
)


def _event_files() -> list[Path]:
    """Tracked ``events.py`` files under ``<bc>/aggregates/<agg>/events.py``."""
    return sorted(
        f
        for f in tracked_python_files()
        if f.name == "events.py"
        and f.parent.parent.name == "aggregates"
        and f.parent.parent.parent.parent == CORA_ROOT
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _unwrap_optional(ann: ast.expr) -> ast.expr:
    """Return the inner type of ``X | None`` (matches CORA's annotation style)."""
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        # X | None  →  take the X side.
        if isinstance(ann.right, ast.Constant) and ann.right.value is None:
            return ann.left
        if isinstance(ann.left, ast.Constant) and ann.left.value is None:
            return ann.right
    return ann


def _mutable_collection_name(ann: ast.expr) -> str | None:
    """Return ``'list'`` / ``'set'`` if ``ann`` is one of those, else ``None``."""
    inner = _unwrap_optional(ann)
    if (
        isinstance(inner, ast.Subscript)
        and isinstance(inner.value, ast.Name)
        and inner.value.id in {"list", "set"}
    ):
        return inner.value.id
    return None


@pytest.mark.architecture
@pytest.mark.parametrize("events_file", _event_files(), ids=_qualified)
def test_event_payload_collection_fields_are_immutable(events_file: Path) -> None:
    qualified_module = _qualified(events_file)
    tree = ast.parse(events_file.read_text())
    violations: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue
            collection = _mutable_collection_name(stmt.annotation)
            if collection is None:
                continue
            key = f"{qualified_module}.{node.name}.{stmt.target.id}"
            if key in MUTABLE_COLLECTION_EVENT_FIELDS:
                continue
            replacement = "tuple[X, ...]" if collection == "list" else "frozenset[X]"
            violations.append(
                f"line {stmt.lineno}: {node.name}.{stmt.target.id} "
                f"is {collection}[...]; use {replacement}"
            )
    assert not violations, (
        f"{qualified_module} has mutable collection fields in event "
        f"payload(s):\n  " + "\n  ".join(violations) + "\n"
        "Event payloads share references into folded state; mutable "
        "collections invite alias bugs. Use tuple / frozenset."
    )


@pytest.mark.architecture
def test_allowlisted_event_fields_actually_exist() -> None:
    """``MUTABLE_COLLECTION_EVENT_FIELDS`` entries must point at real fields."""
    for entry in MUTABLE_COLLECTION_EVENT_FIELDS:
        # entry format: cora.<bc>.aggregates.<agg>.events.<Class>.<field>
        module_parts = entry.split(".")
        # Last two parts are <Class>.<field>; everything before is module path.
        *module_path, class_name, field_name = module_parts
        assert module_path[0] == "cora", f"{entry}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*module_path[1:]).with_suffix(".py")
        assert path.is_file(), f"{entry}: file no longer exists; remove allowlist entry"
        tree = ast.parse(path.read_text())
        cls = next(
            (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name),
            None,
        )
        assert cls is not None, (
            f"{entry}: class {class_name} no longer defined; remove allowlist entry"
        )
        fields = {
            s.target.id
            for s in cls.body
            if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
        }
        assert field_name in fields, (
            f"{entry}: field {field_name} no longer declared; remove allowlist entry"
        )
