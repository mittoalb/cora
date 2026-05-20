"""Per-BC unit-test helper files are named `_helpers.py`.

Top-level shared helpers live at `tests/unit/_helpers.py` and
`tests/integration/_helpers.py`. When a BC accumulates its own seeding
/ setup helpers (typically at rule-of-three), the convention is to
collect them in `tests/unit/<bc>/_helpers.py` — same name as the
top-level shared file, parallel structure across all tiers.

This fitness function rejects divergent names like `_iter2_seed.py`,
`_seed_helpers.py`, `_transition_helpers.py`, `_asset_helper.py` —
each was an isolated authoring choice that left the convention
inconsistent across BCs until 2026-05-18 when they were unified.

The check: any underscore-prefixed `.py` file directly inside a
`tests/unit/<bc>/` directory must be named `_helpers.py` (or be
`__init__.py`). Subdirectories below the BC level (none today, but
allowed) are not policed.
"""

from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_test_files

_TESTS_UNIT_ROOT = Path(__file__).resolve().parents[1] / "unit"

_ALLOWED_HELPER_NAMES: frozenset[str] = frozenset({"_helpers.py", "__init__.py"})


def _bc_helper_files() -> list[Path]:
    """All underscore-prefixed `.py` files directly inside `tests/unit/<bc>/`.

    Enumerates from git's tracked-file set so a half-staged rename
    (old `_seed_helpers.py` deleted-then-stashed, new `_helpers.py`
    untracked) does not false-fail under pre-commit.
    """
    out: list[Path] = []
    for path in sorted(tracked_test_files()):
        if path.parent.parent != _TESTS_UNIT_ROOT:
            continue
        if not (path.name.startswith("_") and path.suffix == ".py"):
            continue
        out.append(path)
    return out


def _qualified(p: Path) -> str:
    rel = p.relative_to(_TESTS_UNIT_ROOT.parent)
    return "/".join(rel.parts)


@pytest.mark.architecture
@pytest.mark.parametrize("helper", _bc_helper_files(), ids=_qualified)
def test_per_bc_helper_named_helpers_py(helper: Path) -> None:
    """Per-BC test-helper file must be named `_helpers.py`.

    Mirrors the top-level convention (`tests/unit/_helpers.py` +
    `tests/integration/_helpers.py`). A descriptive docstring inside the
    file replaces what a descriptive filename would have offered.
    """
    assert helper.name in _ALLOWED_HELPER_NAMES, (
        f"{_qualified(helper)}: per-BC unit-test helper files must be named "
        f"`_helpers.py` (got: {helper.name!r}). Rename via `git mv` and run "
        f"`grep -rl '{_qualified(helper)[:-3].replace('/', '.')}' tests` "
        f"to find imports that need updating."
    )
