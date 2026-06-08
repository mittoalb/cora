"""Pin: structural invariants on the Facility aggregate that the per-aggregate
unit tests do not naturally cover.

Two invariants live here:

  1. The `_FEDERATION_FACILITY_NAMESPACE` UUID constant in
     `cora.federation.aggregates.facility._stream_id` is frozen at its
     original value. Changing it would orphan every existing Facility
     stream (the deterministic uuid5 derivation depends on it). The
     unit test `test_facility_namespace_constant_is_frozen` already
     covers this from the consumer side; this fitness adds a source-
     level guard so an IDE-driven find-and-replace cannot silently
     mutate the literal.

  2. The Facility dataclass declares both fold-symmetric attribution
     pairs: `registered_at` + `registered_by` AND
     `decommissioned_at` + `decommissioned_by`. The
     `test_transversal_fold_symmetry.py` arch fitness covers the
     general rule across all aggregates; this fitness adds a Facility-
     specific source-level pin so a future refactor cannot drop one
     half of either pair without explicitly editing this file.
"""

from __future__ import annotations

import ast
import re

import pytest

from tests.architecture.conftest import CORA_ROOT

_FACILITY_STREAM_ID_PATH = CORA_ROOT / "federation" / "aggregates" / "facility" / "_stream_id.py"
_FACILITY_STATE_PATH = CORA_ROOT / "federation" / "aggregates" / "facility" / "state.py"

_EXPECTED_NAMESPACE_LITERAL = '"01900000-0000-7000-8000-0000fac11111"'
_NAMESPACE_ASSIGNMENT_RE = re.compile(
    r"_FEDERATION_FACILITY_NAMESPACE\s*=\s*UUID\(\s*(\".*?\")\s*\)",
    re.MULTILINE,
)


@pytest.mark.architecture
def test_facility_namespace_literal_is_frozen() -> None:
    """The `_FEDERATION_FACILITY_NAMESPACE` UUID literal MUST be
    byte-identical to its original choice. Mutating it would orphan
    every existing Facility stream (uuid5 derivation depends on it)."""
    source = _FACILITY_STREAM_ID_PATH.read_text()
    match = _NAMESPACE_ASSIGNMENT_RE.search(source)
    assert match is not None, (
        f"{_FACILITY_STREAM_ID_PATH.relative_to(CORA_ROOT)}: "
        'could not find `_FEDERATION_FACILITY_NAMESPACE = UUID("...")` '
        "assignment. The deterministic stream-id derivation depends on "
        "this constant; refactor must preserve the assignment shape."
    )
    found_literal = match.group(1)
    assert found_literal == _EXPECTED_NAMESPACE_LITERAL, (
        f"{_FACILITY_STREAM_ID_PATH.relative_to(CORA_ROOT)}: "
        f"_FEDERATION_FACILITY_NAMESPACE literal drifted from "
        f"{_EXPECTED_NAMESPACE_LITERAL} to {found_literal}. Changing "
        "this value orphans every existing Facility stream (uuid5 "
        "derivation depends on it). Revert the change or coordinate "
        "a full Facility-stream re-derivation migration."
    )


def _find_facility_class(tree: ast.AST) -> ast.ClassDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Facility":
            return node
    msg = "Could not find `class Facility` in facility/state.py"
    raise AssertionError(msg)


def _annotated_field_pairs(class_def: ast.ClassDef) -> dict[str, str]:
    """Return `{field_name: ast.unparse(annotation)}` for every annotated
    assignment on the class body."""
    out: dict[str, str] = {}
    for node in class_def.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = ast.unparse(node.annotation)
    return out


@pytest.mark.architecture
def test_facility_state_declares_both_fold_symmetric_attribution_pairs() -> None:
    """The Facility dataclass MUST carry both fold-symmetric attribution
    pairs: registered_at + registered_by AND decommissioned_at +
    decommissioned_by. Both `_by` fields MUST be typed as `ActorId`
    so the fold-symmetry fitness test detects them structurally."""
    tree = ast.parse(_FACILITY_STATE_PATH.read_text())
    facility_cls = _find_facility_class(tree)
    fields = _annotated_field_pairs(facility_cls)

    required_pairs = {
        "registered_at": "datetime",
        "registered_by": "ActorId",
        "decommissioned_at": "datetime | None",
        "decommissioned_by": "ActorId | None",
    }

    missing: list[str] = []
    wrong_type: list[str] = []
    for field_name, expected_annotation in required_pairs.items():
        if field_name not in fields:
            missing.append(field_name)
            continue
        actual = fields[field_name]
        if actual != expected_annotation:
            wrong_type.append(f"{field_name}: expected `{expected_annotation}`, found `{actual}`")

    problems: list[str] = []
    if missing:
        problems.append(f"missing fields: {missing}")
    if wrong_type:
        problems.append("wrong-type fields:\n    " + "\n    ".join(wrong_type))

    assert not problems, (
        f"{_FACILITY_STATE_PATH.relative_to(CORA_ROOT)}::Facility "
        "fold-symmetry violation:\n  "
        + "\n  ".join(problems)
        + "\n\nPer [[project_fold_symmetry_design]] + [[project_facility_aggregate_design]]: "
        "the Facility aggregate folds both halves of the genesis and "
        "terminal-transition attribution pairs. The `_by` fields MUST "
        "be typed `ActorId` so the cross-aggregate fold-symmetry fitness "
        "test detects them structurally rather than by name."
    )
