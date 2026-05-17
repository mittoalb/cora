"""Pin: any module constructing Caution events must call the invariants module.

Background: commit `cfc9540` restored the supersede target-stability
guard on the cross-BC `promote_caution_proposal` handler after the
Pattern C refactor (`b6c8e0a`) silently dropped it. The invariants
were hand-replicated in prose. This test makes the regression class
structurally unrepresentable.

Rule: any `.py` file under `cora/**` that constructs a
`CautionSuperseded(...)` MUST also import `ensure_supersedable` and
`ensure_target_preserved` from `cora.caution.aggregates.caution`.
Any file that constructs a `CautionRegistered(...)` MUST also import
`ensure_expires_at_future`. The aggregate-kernel module that
*defines* the events is exempt.

The test does not assert the invariants are actually called — only
that they are imported. Two reasons:

  - AST call-flow analysis is fragile (the invariant may legitimately
    be called from a helper one level up).
  - The intent IS that human review + pyright catch un-used imports
    via ruff (F401 already enabled), so an unused-but-imported guard
    fails CI elsewhere.

Sibling-BC handlers constructing Caution events use the same
aggregate-public-surface import path the Caution BC's own deciders
use; nothing in this test is BC-specific. Whenever a new event type
joins `Caution*` with non-trivial invariants, extend `_RULES`.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT

# Files under `cora.caution.aggregates.caution.*` define the event
# classes; they don't need to import the invariants module (it sits
# beside them). Tests are excluded from architecture scans elsewhere
# and won't appear under `cora/`.
_DEFINER_PREFIX = "cora.caution.aggregates.caution"


# Each rule: constructing this event class requires importing at
# least these symbol names from `cora.caution.aggregates.caution`.
_RULES: dict[str, frozenset[str]] = {
    "CautionSuperseded": frozenset({"ensure_supersedable", "ensure_target_preserved"}),
    "CautionRegistered": frozenset({"ensure_expires_at_future"}),
}


def _all_python_files() -> list[Path]:
    return sorted(CORA_ROOT.rglob("*.py"))


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _imported_symbols_from(tree: ast.AST, module_prefix: str) -> set[str]:
    """Symbols imported via `from <module_prefix>[.subpkg] import X, Y, ...`."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (node.module == module_prefix or node.module.startswith(module_prefix + "."))
        ):
            for alias in node.names:
                out.add(alias.name)
    return out


def _constructed_class_names(tree: ast.AST) -> set[str]:
    """Names of classes constructed via `Name(...)` calls in this file.

    Matches the common `from X import Foo; Foo(...)` shape. Does not
    attempt to resolve `module.Foo(...)`; those cases are exceedingly
    rare in CORA's slice files and would surface elsewhere (an
    unused-import warning, a tach violation).
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            out.add(node.func.id)
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("path", _all_python_files(), ids=_qualified)
def test_caution_event_constructors_import_invariants(path: Path) -> None:
    """If you construct a Caution event, you import its invariants module."""
    qualified = _qualified(path)
    if qualified.startswith(_DEFINER_PREFIX):
        return

    tree = ast.parse(path.read_text())
    constructed = _constructed_class_names(tree)
    relevant = constructed & _RULES.keys()
    if not relevant:
        return

    imported = _imported_symbols_from(tree, "cora.caution.aggregates.caution")
    missing: list[str] = []
    for event_name in sorted(relevant):
        required = _RULES[event_name]
        absent = required - imported
        if absent:
            missing.append(
                f"constructs {event_name}; missing import(s): " + ", ".join(sorted(absent))
            )

    assert not missing, (
        f"{qualified} constructs Caution events without importing the "
        "invariants module:\n  " + "\n  ".join(missing) + "\n"
        "Import the missing predicates from `cora.caution.aggregates.caution` "
        "and call them at every write site. See "
        "`cora/caution/aggregates/caution/invariants.py` for the rationale "
        "(commit cfc9540 is the regression this pin prevents)."
    )
