"""Pin: dataclass fields holding `frozenset[UUID]` / `tuple[UUID, ...]` end in `_ids`.

The naming-audit field-suffix sweep normalized every UUID-collection
field on the codebase to the `<role>_<entity>_ids` shape:
`Method.needed_family_ids`,
`Permit.allowed_credential_ids`, `Policy.permitted_principal_ids`,
`Run.pinned_calibration_ids`, `Dataset.used_calibration_ids`,
`Asset.family_ids`, `Plan.asset_ids`, `Campaign.run_ids`, etc.

This fitness function keeps the shape sticky. Any new aggregate /
event field declaring a UUID collection must use the suffix. If a
genuinely standards-bound term ships in a future field (PROV-O,
PIDINST, RO-Crate vocabulary), extend `_CARVE_OUTS` with the exact
field name AND add the rationale in `docs/reference/conventions.md`.

Scope: dataclass field declarations in `cora/*/aggregates/*/events.py`
and `cora/*/aggregates/*/state.py`. Function parameters and local
variables are not in scope; the convention is about the persistent
shape of the aggregate state and the event payload that mirrors it.

Carve-outs:
  - `derived_from` on Dataset (PROV-O standard term; preserves
    `prov:wasDerivedFrom` for future RO-Crate / PROV-O export).
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_BANNED_BARE_ANNOTATIONS: frozenset[str] = frozenset(
    {
        "frozenset[UUID]",
        "tuple[UUID, ...]",
    }
)

_CARVE_OUTS: frozenset[str] = frozenset(
    {
        "derived_from",  # Dataset (PROV-O wasDerivedFrom)
    }
)


def _aggregate_state_or_events_files() -> list[Path]:
    return sorted(
        path
        for path in tracked_python_files()
        if path.name in {"events.py", "state.py"} and "/aggregates/" in str(path)
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _uuid_collection_fields(tree: ast.AST) -> list[tuple[str, str, int]]:
    """Return (class_name, field_name, lineno) for every dataclass field
    annotated as a banned UUID-collection shape (frozenset[UUID] or
    tuple[UUID, ...])."""
    out: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                continue
            annotation = ast.unparse(item.annotation).replace(" ", "")
            normalized = annotation.replace("...,", "...").replace(" ", "")
            for banned in _BANNED_BARE_ANNOTATIONS:
                if banned.replace(" ", "") == normalized:
                    out.append((node.name, item.target.id, item.lineno))
                    break
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("path", _aggregate_state_or_events_files(), ids=_qualified)
def test_uuid_collection_field_names_end_in_ids(path: Path) -> None:
    """Every frozenset[UUID] / tuple[UUID, ...] field must end in `_ids`."""
    tree = ast.parse(path.read_text())
    fields = _uuid_collection_fields(tree)
    offenders: list[str] = []
    for class_name, field_name, lineno in fields:
        if field_name in _CARVE_OUTS:
            continue
        # Accept `_ids` either at the end (asset_ids) or as an interior
        # underscore-bounded token (method_needed_family_ids_snapshot,
        # where the structural _snapshot suffix marks the captured-at-time
        # variant of the underlying _ids field).
        if "ids" not in field_name.split("_"):
            offenders.append(f"line {lineno}: {class_name}.{field_name}")
    assert not offenders, (
        f"{_qualified(path)} declares UUID-collection field(s) without an `_ids` suffix:\n  "
        + "\n  ".join(offenders)
        + "\n\nFields of type `frozenset[UUID]` or `tuple[UUID, ...]` are foreign-key "
        "collections; the `_ids` suffix marks them as such and keeps them grep-symmetric "
        "with their singular siblings (`parent_id`, `caution_id`, etc.). If a new field "
        "must keep a standards-bound bare-plural name (PROV-O, PIDINST, etc.), add it to "
        "`_CARVE_OUTS` in this file AND document the rationale in "
        "`docs/reference/conventions.md` under Code identifier carve-outs."
    )
