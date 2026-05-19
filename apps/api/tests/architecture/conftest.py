"""Shared roots and helpers for architecture fitness-function tests.

These tests run alongside the rest of the suite (`pytest` picks
them up automatically) but enforce structural invariants the
import graph + AST + filesystem can prove. Tach (`tach.toml` at
the apps/api root) handles dependency-graph rules; everything
under this directory handles the rules tach can't express:
slice file contracts, decider purity, completeness-of-wiring.

`SRC_ROOT` is computed relative to this file so tests work
whether pytest is invoked from `apps/api/` (the Makefile target)
or from the repository root (CI).

## Slice enumeration is git-aware, not filesystem-aware

`tracked_python_files()` returns the set of `.py` files under
`src/cora` that git is tracking. Architecture tests that enumerate
slices MUST filter by this set rather than scan the filesystem
directly. Reason: pre-commit only stashes unstaged changes to
**tracked** files (issues #1212, #708 — maintainer rejected
untracked-stash twice because it would clobber local venvs / tox
state). Untracked files stay live on disk during hook runs. A
filesystem scan therefore sees half-staged slices (untracked
handler.py + stashed wire.py edits hidden) and false-fails
wire-completeness / contract checks. Filtering through git's
tracked-file list mirrors what pre-commit actually evaluates:
new slices in flight stay invisible until `git add`ed, at which
point all the usual invariants kick in.
"""

import subprocess
from functools import cache
from pathlib import Path

# tests/architecture/conftest.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]

SRC_ROOT = _API_ROOT / "src"
CORA_ROOT = SRC_ROOT / "cora"

BCS: tuple[str, ...] = (
    "access",
    "agent",
    "calibration",
    "campaign",
    "caution",
    "data",
    "decision",
    "equipment",
    "operation",
    "recipe",
    "run",
    "safety",
    "subject",
    "supply",
    "trust",
)


@cache
def tracked_python_files() -> frozenset[Path]:
    """Absolute paths to git-tracked `.py` files under `src/cora`.

    See module docstring for why architecture fitness functions
    must enumerate from this set rather than from filesystem scans.
    Cached because pytest collection invokes the slice enumerators
    multiple times.
    """
    result = subprocess.run(
        ["git", "ls-files", "src/cora"],
        cwd=_API_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return frozenset(
        _API_ROOT / line for line in result.stdout.splitlines() if line.endswith(".py")
    )
