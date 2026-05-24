"""Every decider carries an ``Invariants:`` block listing its rejections.

Per ``docs/reference/patterns.md``:

  > Decider docstrings carry an ``Invariants:`` block listing each
  > rejection inline with its exception name. This is the contract;
  > downstream readers (test author, API consumer) shouldn't have to
  > re-derive it from the body.

Detection is **file-level**: the string ``"Invariants:"`` appears
anywhere in the decider's text (module docstring OR ``decide`` function
docstring). The patterns.md example shows the block inside the
function's docstring, but the older convention placed it in the module
docstring; both are accepted today. A future phase can tighten this to
the function-docstring-only form once the existing files are aligned.

``DECIDERS_MISSING_INVARIANTS`` is the explicit allowlist for
deciders without the block. Currently empty: every decider
complies. The drift catcher stays armed so any new decider that
ships without the block fails at PR time. The test fails BOTH
ways: a missing decider that's not allowlisted, AND an allowlisted
decider that now has the block (so the allowlist can't go stale).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


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
