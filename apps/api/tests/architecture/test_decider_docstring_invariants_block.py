"""Every decider carries an ``Invariants:`` block listing its rejections.

Per ``docs/reference/patterns.md``:

  > Decider docstrings carry an ``Invariants:`` block listing each
  > rejection inline with its exception name. This is the contract;
  > downstream readers (test author, API consumer) shouldn't have to
  > re-derive it from the body.

Two complementary checks live here:

  1. **Placement** (``test_decider_carries_invariants_block``):
     ``"Invariants:"`` appears anywhere in the decider's text
     (module docstring OR ``decide`` function docstring). The
     patterns.md example shows the block inside the function's
     docstring, but the older convention placed it in the module
     docstring; both are accepted today. A future phase can tighten
     this to the function-docstring-only form once the existing
     files are aligned.

  2. **Raise/enumerate sync** (``test_decider_invariants_enumerate_explicit_raises``):
     every ``raise <SomethingError>(...)`` in the ``decide`` body
     must be enumerated by name (``-> SomethingError``) in the
     Invariants block. Catches docstring drift when a new guard is
     added to the body but the contract isn't updated. The reverse
     direction (enumerated entries that have no ``raise`` in the
     body) is NOT asserted: VOs and ``validate_*`` helpers raise
     legitimately-enumerated errors without an explicit ``raise``
     in the decider's source.

``DECIDERS_MISSING_INVARIANTS`` is the explicit allowlist for
deciders without the block. Currently empty: every decider
complies. The drift catcher stays armed so any new decider that
ships without the block fails at PR time. The test fails BOTH
ways: a missing decider that's not allowlisted, AND an allowlisted
decider that now has the block (so the allowlist can't go stale).
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


_ENUMERATED_ERROR = re.compile(r"->\s*(\w+Error)\b")


# Empty allowlist: every decider carries the Invariants block. Add
# an entry only when grandfathering a new violator ahead of its
# documentation pass; remove it when the block lands.
DECIDERS_MISSING_INVARIANTS: frozenset[str] = frozenset()


def _decider_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        out.extend(
            sorted(
                f
                for f in tracked
                if f.name == "decider.py"
                and f.parent.parent == features
                and not f.parent.name.startswith("_")
            )
        )
    return out


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _decider_files(), ids=_qualified)
def test_decider_carries_invariants_block(decider: Path) -> None:
    qualified = _qualified(decider)
    has_invariants = "Invariants:" in decider.read_text()
    in_allowlist = qualified in DECIDERS_MISSING_INVARIANTS

    if in_allowlist:
        assert not has_invariants, (
            f"{qualified}: now has `Invariants:` block; remove from "
            "DECIDERS_MISSING_INVARIANTS in test_decider_docstring_invariants_block.py."
        )
    else:
        assert has_invariants, (
            f"{qualified}: decider missing `Invariants:` block. "
            "Per docs/reference/patterns.md, every decider docstring "
            "enumerates rejections inline with each exception name."
        )


@pytest.mark.architecture
def test_allowlisted_deciders_actually_exist() -> None:
    """``DECIDERS_MISSING_INVARIANTS`` entries must point at real files."""
    for qualified in DECIDERS_MISSING_INVARIANTS:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert path.is_file(), (
            f"DECIDERS_MISSING_INVARIANTS entry {qualified} no longer exists; remove it"
        )


def _raised_error_names(decide_fn: ast.FunctionDef) -> set[str]:
    """Collect names of exception classes explicitly raised in `decide`.

    Walks the function body for `raise <Name>(...)` and
    `raise <Mod>.<Name>(...)` patterns where the symbol ends in
    ``Error``. Bare `raise` (re-raise) is skipped: no class name to
    pin against the docstring.
    """
    raised: set[str] = set()
    for node in ast.walk(decide_fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc
        func = exc.func if isinstance(exc, ast.Call) else exc
        if isinstance(func, ast.Name) and func.id.endswith("Error"):
            raised.add(func.id)
        elif isinstance(func, ast.Attribute) and func.attr.endswith("Error"):
            raised.add(func.attr)
    return raised


def _invariants_docstring(decider_path: Path) -> str | None:
    """Return whichever docstring carries the ``Invariants:`` block.

    Function docstring wins when both contain it (the patterns.md
    canonical form). Returns ``None`` when neither does: that case
    is already covered by ``test_decider_carries_invariants_block``
    and the sync test should skip rather than double-report.
    """
    tree = ast.parse(decider_path.read_text())
    module_doc = ast.get_docstring(tree) or ""
    decide_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "decide":
            decide_fn = node
            break
    func_doc = ast.get_docstring(decide_fn) if decide_fn is not None else ""
    func_doc = func_doc or ""
    if "Invariants:" in func_doc:
        return func_doc
    if "Invariants:" in module_doc:
        return module_doc
    return None


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _decider_files(), ids=_qualified)
def test_decider_invariants_enumerate_explicit_raises(decider: Path) -> None:
    """Every ``raise <SomeError>(...)`` in ``decide`` is enumerated in Invariants.

    Drift catcher: when a new guard is added to the decider body
    without updating the ``-> <ErrorName>`` line in the Invariants
    block, the docstring contract silently lies. This test fails
    the PR before the lie ships.

    Reverse direction (enumerated entry has no matching ``raise``)
    is NOT asserted: VOs (``DecisionChoice("...")``) and
    ``validate_*`` helpers legitimately raise enumerated errors
    without an explicit ``raise`` in the decider's source. The
    docstring is the union; the body is a subset.
    """
    qualified = _qualified(decider)
    if qualified in {f"cora.{q}" for q in DECIDERS_MISSING_INVARIANTS}:
        pytest.skip(f"{qualified}: allowlisted as missing Invariants block")

    tree = ast.parse(decider.read_text())
    decide_fn = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "decide"),
        None,
    )
    if decide_fn is None:
        pytest.skip(f"{qualified}: no `decide` function (validator-shaped slice)")

    inv_doc = _invariants_docstring(decider)
    if inv_doc is None:
        pytest.skip(
            f"{qualified}: no Invariants block found "
            "(covered by test_decider_carries_invariants_block)"
        )

    enumerated = set(_ENUMERATED_ERROR.findall(inv_doc))
    raised = _raised_error_names(decide_fn)
    missing = sorted(raised - enumerated)

    assert not missing, (
        f"{qualified}: the following errors are raised in `decide` but not "
        f"enumerated in the Invariants block: {missing}.\n"
        "Add a `- <description> -> <ErrorName>` line for each, or remove "
        "the raise. The Invariants block is the published contract; it "
        "must list every error path that surfaces to the caller."
    )
